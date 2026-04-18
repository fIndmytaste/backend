"""
Vendor discovery helpers shared across all vendor views.

Ordering guarantee (nearest-first):
  1. Redis GEORADIUS  — O(log N + M), zero Python loops, scales to millions of vendors
  2. Haversine fallback — used only when Redis is unreachable
"""

from django.db.models import Count, Q

from account.models import Address, Vendor
from helpers.order_utils import get_distance_between_two_location
from helpers.redis_geo import geo_nearby_vendor_ids, BROWSE_RADIUS_KM, SEARCH_RADIUS_KM


# ---------------------------------------------------------------------------
# Queryset helpers
# ---------------------------------------------------------------------------

def approved_vendor_queryset(queryset=None, *, require_products=True, require_location=False):
    queryset = queryset if queryset is not None else Vendor.objects.all()
    queryset = queryset.filter(
        approval_status='approved',
        is_active=True,
    )

    if require_location:
        queryset = queryset.filter(
            location_latitude__isnull=False,
            location_longitude__isnull=False,
        )

    if require_products:
        queryset = queryset.annotate(product_count=Count('product')).filter(
            product_count__gt=0,
        )

    return queryset.distinct()


def apply_vendor_search(queryset, search):
    if not search:
        return queryset

    return queryset.filter(
        Q(name__icontains=search)
        | Q(email__icontains=search)
        | Q(city__icontains=search)
        | Q(state__icontains=search)
        | Q(category__name__icontains=search)
    )


def resolve_request_coordinates(request):
    query_latitude = request.GET.get('latitude')
    query_longitude = request.GET.get('longitude')

    if query_latitude and query_longitude:
        try:
            return float(query_latitude), float(query_longitude)
        except (TypeError, ValueError):
            return None, None

    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return None, None

    address = (
        Address.objects.filter(user=user, is_active=True)
        .order_by('-is_primary', '-updated_at')
        .first()
    )
    if not address or address.location_latitude is None or address.location_longitude is None:
        return None, None

    try:
        return float(address.location_latitude), float(address.location_longitude)
    except (TypeError, ValueError):
        return None, None


# ---------------------------------------------------------------------------
# Core sort: Redis geo first, Haversine fallback
# ---------------------------------------------------------------------------

def filter_and_sort_vendors_by_distance(
    vendors,
    user_latitude,
    user_longitude,
    *,
    enforce_delivery_radius=True,
    radius_km=BROWSE_RADIUS_KM,
):
    """
    Return [(vendor, distance_km), ...] sorted nearest-first.

    radius_km controls how far Redis searches:
      - BROWSE_RADIUS_KM (10km) for home feed, hot-picks, featured, all-vendors
      - SEARCH_RADIUS_KM (500km) for keyword search (relevance drives results)

    enforce_delivery_radius=True is used only for order placement eligibility.
    For browsing, always False — we filter by radius_km instead.
    """
    if user_latitude is None or user_longitude is None:
        return list(vendors)

    vendor_list = list(vendors)
    if not vendor_list:
        return []

    # --- Path 1: Redis geo ---
    nearby = geo_nearby_vendor_ids(user_latitude, user_longitude, radius_km=radius_km)

    if nearby is not None:
        vendor_map = {str(v.id): v for v in vendor_list}
        results = []
        for vendor_id, dist_km in nearby:
            vendor = vendor_map.get(vendor_id)
            if vendor is None:
                continue
            if enforce_delivery_radius and dist_km > float(vendor.delivery_radius_km):
                continue
            vendor.distance_km = round(dist_km, 2)
            results.append((vendor, dist_km))
        results.sort(key=lambda item: (item[1], -(float(item[0].rating or 0)), item[0].name or ''))
        return results

    # --- Path 2: Haversine fallback (Redis down) ---
    vendors_with_distance = []
    for vendor in vendor_list:
        try:
            distance = get_distance_between_two_location(
                lat1=user_latitude,
                lon1=user_longitude,
                lat2=float(vendor.location_latitude),
                lon2=float(vendor.location_longitude),
            )
        except (TypeError, ValueError):
            continue

        if distance is None:
            continue

        # Apply the same radius cap as Redis would
        if distance > radius_km and not enforce_delivery_radius:
            continue

        if enforce_delivery_radius and distance > float(vendor.delivery_radius_km):
            continue

        vendor.distance_km = round(distance, 2)
        vendors_with_distance.append((vendor, distance))

    vendors_with_distance.sort(
        key=lambda item: (
            item[1],
            -(float(item[0].rating or 0)),
            item[0].name or '',
        )
    )
    return vendors_with_distance


def nearest_first_vendors(
    vendors,
    user_latitude,
    user_longitude,
    *,
    enforce_delivery_radius=True,
    radius_km=BROWSE_RADIUS_KM,
):
    return [
        vendor
        for vendor, _ in filter_and_sort_vendors_by_distance(
            vendors,
            user_latitude,
            user_longitude,
            enforce_delivery_radius=enforce_delivery_radius,
            radius_km=radius_km,
        )
    ]
