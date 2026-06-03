"""
Redis Geo service for rider dispatch proximity queries.

This mirrors the vendor geo approach, but keeps rider lookup optimized for
dispatch fanout: find all online riders in expanding neighborhood bands around
the vendor and let the database remain the final source of truth for claiming.
"""

import logging
import time
from typing import Iterable, Optional

from helpers.redis_geo import _get_redis_client

logger = logging.getLogger(__name__)

RIDER_GEO_KEY = "riders:geo"
RIDER_GEO_FRESHNESS_KEY = "riders:geo:freshness"
RIDER_GEO_FRESHNESS_SECONDS = 120


def geo_add_rider(rider) -> bool:
    """
    Add or update a rider in the Redis geo index.
    Only online riders with coordinates should be indexed.
    """
    if not rider.is_online:
        return geo_remove_rider(rider.id)

    latitude = rider.current_latitude or rider.location_latitude
    longitude = rider.current_longitude or rider.location_longitude
    if latitude is None or longitude is None:
        return False

    r = _get_redis_client()
    if r is None:
        return False

    try:
        now_ts = int(time.time())
        pipe = r.pipeline()
        pipe.execute_command("GEOADD", RIDER_GEO_KEY, float(longitude), float(latitude), str(rider.id))
        pipe.zadd(RIDER_GEO_FRESHNESS_KEY, {str(rider.id): now_ts})
        pipe.execute()
        return True
    except Exception as exc:
        logger.warning("geo_add_rider failed for %s: %s", rider.id, exc)
        return False


def geo_remove_rider(rider_id) -> bool:
    """
    Remove a rider from the Redis geo index.
    """
    r = _get_redis_client()
    if r is None:
        return False

    try:
        pipe = r.pipeline()
        pipe.zrem(RIDER_GEO_KEY, str(rider_id))
        pipe.zrem(RIDER_GEO_FRESHNESS_KEY, str(rider_id))
        pipe.execute()
        return True
    except Exception as exc:
        logger.warning("geo_remove_rider failed for %s: %s", rider_id, exc)
        return False


def cleanup_stale_riders(max_age_seconds: int = RIDER_GEO_FRESHNESS_SECONDS) -> int:
    """
    Remove stale riders from the geo index using the Redis freshness sorted set.
    """
    r = _get_redis_client()
    if r is None:
        return 0

    stale_before = int(time.time()) - max_age_seconds
    try:
        stale_rider_ids = [
            rider_id.decode() if isinstance(rider_id, bytes) else str(rider_id)
            for rider_id in r.zrangebyscore(RIDER_GEO_FRESHNESS_KEY, 0, stale_before)
        ]
        if not stale_rider_ids:
            return 0

        pipe = r.pipeline()
        pipe.zrem(RIDER_GEO_KEY, *stale_rider_ids)
        pipe.zrem(RIDER_GEO_FRESHNESS_KEY, *stale_rider_ids)
        pipe.execute()
        return len(stale_rider_ids)
    except Exception as exc:
        logger.warning("cleanup_stale_riders failed: %s", exc)
        return 0


def geo_nearby_rider_ids(
    vendor_lat: float,
    vendor_lon: float,
    radii_km: Iterable[float],
) -> Optional[list[tuple[str, float]]]:
    """
    Query riders in expanding neighborhood radii around a vendor.

    Returns ordered unique (rider_id, distance_km) pairs, nearest bands first,
    or None if Redis is unavailable so callers can fall back.
    """
    r = _get_redis_client()
    if r is None:
        return None

    try:
        cleanup_stale_riders()
        seen: dict[str, float] = {}
        ordered: list[tuple[str, float]] = []
        for radius_km in radii_km:
            raw = r.georadius(
                RIDER_GEO_KEY,
                vendor_lon,
                vendor_lat,
                radius_km,
                "km",
                withdist=True,
                withcoord=False,
                sort="ASC",
            )
            for member, dist in raw:
                rider_id = member.decode()
                distance_km = float(dist)
                if rider_id in seen:
                    continue
                seen[rider_id] = distance_km
                ordered.append((rider_id, distance_km))
        return ordered
    except Exception as exc:
        logger.warning("Redis rider geo query failed, will fall back to DB scan: %s", exc)
        return None


def rebuild_rider_geo_index(riders) -> tuple[int, int]:
    """
    Rebuild the rider geo index from a queryset/iterable of rider objects.

    Returns (indexed_count, skipped_count).
    """
    r = _get_redis_client()
    if r is None:
        return 0, 0

    indexed = 0
    skipped = 0
    now_ts = int(time.time())
    try:
        pipe = r.pipeline()
        pipe.delete(RIDER_GEO_KEY)
        pipe.delete(RIDER_GEO_FRESHNESS_KEY)

        for rider in riders:
            latitude = rider.current_latitude or rider.location_latitude
            longitude = rider.current_longitude or rider.location_longitude
            if (
                not rider.is_online
                or latitude is None
                or longitude is None
            ):
                skipped += 1
                continue

            pipe.execute_command("GEOADD", RIDER_GEO_KEY, float(longitude), float(latitude), str(rider.id))
            timestamp = rider.location_updated_at.timestamp() if rider.location_updated_at else now_ts
            pipe.zadd(RIDER_GEO_FRESHNESS_KEY, {str(rider.id): int(timestamp)})
            indexed += 1

        pipe.execute()
        return indexed, skipped
    except Exception as exc:
        logger.warning("rebuild_rider_geo_index failed: %s", exc)
        return 0, 0
