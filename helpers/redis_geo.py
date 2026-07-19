"""
Redis Geo service for vendor proximity queries.

All vendor discovery views use this module so geo logic lives in one place.

Key design decisions:
- GEO index key: "vendors:geo"  (stores approved + active vendors with coordinates)
- Search radius: 500 km ceiling — wide enough for any real use, Redis filters fast
- enforce_delivery_radius: optionally applies each vendor's delivery cap in
                           addition to the endpoint's browse/search radius
- Fallback: if Redis is unreachable, falls back to the shared Haversine helper
            so the app never goes dark
"""

import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

GEO_KEY = "vendors:geo"
GEO_INDEX_VALIDATION_KEY = "vendors:geo:validated"
GEO_INDEX_VALIDATION_TTL_SECONDS = 5 * 60

# Browsing radius: vendors shown on home feed, hot-picks, featured, all-vendors.
# 10km matches what Chowdeck/Bolt Food use for Nigerian city density —
# tight enough to be relevant, wide enough to cover a full city.
BROWSE_RADIUS_KM = 10

# Wide radius used only for explicit search (user typed a keyword).
# We let the search query itself be the relevance filter.
SEARCH_RADIUS_KM = 500


def _get_redis_client():
    """Return a raw redis.Redis client from the Django cache URL, or None."""
    try:
        import redis as redis_lib
        location = settings.CACHES["default"].get("LOCATION")
        if not location:
            return None
        client = redis_lib.Redis.from_url(location, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


def _eligible_geo_vendors():
    """Return every vendor that should have coordinates in the geo index."""
    from account.models import Vendor

    return list(
        Vendor.objects.filter(
            approval_status='approved',
            is_active=True,
            location_latitude__isnull=False,
            location_longitude__isnull=False,
        ).exclude(
            location_latitude='',
            location_longitude='',
        )
    )


def _decode_member(member) -> str:
    return member.decode() if isinstance(member, bytes) else str(member)


def _rebuild_geo_index(r, vendors=None) -> int:
    """
    Repopulate the geo index from the database.

    Render's Redis is not persistent: a restart or cache eviction can drop the
    "vendors:geo" key at any time, which previously made every discovery
    endpoint return an empty list ("no vendors nearby") until someone manually
    ran populate_redis_geo. Rebuilding lazily here makes the index self-heal.

    Returns the number of vendors indexed.
    """
    vendors = _eligible_geo_vendors() if vendors is None else list(vendors)

    pipe = r.pipeline()
    # Delete and repopulate in one pipeline so stale members are removed too.
    pipe.delete(GEO_KEY)
    added = 0
    for vendor in vendors:
        try:
            lon = float(vendor.location_longitude)
            lat = float(vendor.location_latitude)
        except (TypeError, ValueError):
            continue
        pipe.execute_command("GEOADD", GEO_KEY, lon, lat, str(vendor.id))
        added += 1

    # Execute even when there are no eligible vendors so a stale index is cleared.
    pipe.execute()
    logger.warning("Rebuilt vendors:geo with %s vendors", added)
    return added


def _ensure_geo_index(r) -> bool:
    """
    Validate Redis membership against the database and repair it when needed.

    Validation is cached briefly to keep the normal request path fast. Vendor
    save/remove operations invalidate the marker, so ordinary data changes are
    checked on the very next discovery request.
    """
    try:
        if r.exists(GEO_KEY) and r.get(GEO_INDEX_VALIDATION_KEY):
            return True

        vendors = _eligible_geo_vendors()
        expected_ids = {str(vendor.id) for vendor in vendors}
        indexed_ids = {
            _decode_member(member)
            for member in r.zrange(GEO_KEY, 0, -1)
        }

        if indexed_ids != expected_ids:
            _rebuild_geo_index(r, vendors=vendors)

        r.set(
            GEO_INDEX_VALIDATION_KEY,
            "1",
            ex=GEO_INDEX_VALIDATION_TTL_SECONDS,
        )
        return True
    except Exception as exc:
        logger.warning("Redis geo index validation/rebuild failed: %s", exc)
        return False


def geo_nearby_vendor_ids(
    user_lat: float,
    user_lon: float,
    radius_km: float = BROWSE_RADIUS_KM,
) -> Optional[list[tuple[str, float]]]:
    """
    Query Redis GEOSEARCH for vendors within radius_km of the user.

    Returns a list of (vendor_id_str, distance_km) tuples sorted nearest-first,
    or None if Redis is unavailable (caller should fall back to Haversine).
    """
    r = _get_redis_client()
    if r is None:
        return None

    # Redis is an acceleration layer, never the source of truth. If validation
    # cannot complete, let the caller use its database/Haversine fallback.
    if not _ensure_geo_index(r):
        return None

    try:
        # GEORADIUS is deprecated in Redis 6.2+ but widely supported.
        # We use the lower-level execute_command so we work on all versions.
        raw = r.georadius(
            GEO_KEY,
            user_lon,   # Redis wants (lon, lat)
            user_lat,
            radius_km,
            "km",
            withdist=True,
            withcoord=False,
            sort="ASC",
        )
        # raw: [(b'uuid', distance_float), ...]
        return [(member.decode(), float(dist)) for member, dist in raw]
    except Exception as exc:
        logger.warning("Redis geo query failed, will fall back to Haversine: %s", exc)
        return None


def geo_add_vendor(vendor) -> bool:
    """
    Add or update a single vendor in the Redis geo index.
    Safe to call on vendor save — no-ops if Redis is down.
    """
    r = _get_redis_client()
    if r is None:
        return False

    try:
        lat = float(vendor.location_latitude)
        lon = float(vendor.location_longitude)
        r.execute_command("GEOADD", GEO_KEY, lon, lat, str(vendor.id))
        r.delete(GEO_INDEX_VALIDATION_KEY)
        return True
    except Exception as exc:
        try:
            r.delete(GEO_INDEX_VALIDATION_KEY)
        except Exception:
            pass
        logger.warning("geo_add_vendor failed for %s: %s", vendor.id, exc)
        return False


def geo_remove_vendor(vendor_id: str) -> bool:
    """
    Remove a vendor from the Redis geo index (called on deactivation / rejection).
    """
    r = _get_redis_client()
    if r is None:
        return False

    try:
        r.zrem(GEO_KEY, str(vendor_id))
        r.delete(GEO_INDEX_VALIDATION_KEY)
        return True
    except Exception as exc:
        try:
            r.delete(GEO_INDEX_VALIDATION_KEY)
        except Exception:
            pass
        logger.warning("geo_remove_vendor failed for %s: %s", vendor_id, exc)
        return False


def resolve_vendor_ids_from_geo(
    user_lat: float,
    user_lon: float,
    enforce_delivery_radius: bool,
    vendor_map: dict,  # {vendor_id_str: Vendor}
) -> list[tuple]:
    """
    Given a geo result and a dict of vendor objects, return
    (vendor, distance_km) pairs, optionally filtered by delivery radius,
    sorted nearest-first.
    """
    nearby = geo_nearby_vendor_ids(user_lat, user_lon)
    if nearby is None:
        return None  # Signal to caller: Redis unavailable

    results = []
    for vendor_id, dist_km in nearby:
        vendor = vendor_map.get(vendor_id)
        if vendor is None:
            continue
        if enforce_delivery_radius and dist_km > float(vendor.delivery_radius_km):
            continue
        import decimal
        vendor.distance_km = round(dist_km, 2)
        results.append((vendor, dist_km))

    return results
