"""
Admin Analytics: Customer Location & Demand Intelligence
=========================================================
Endpoints:
  GET /admin-manager/analytics/user-locations/
      Returns user registrations grouped by city/area, with lat/lon centroid
      and a count. Filterable by state, city, date range.

  GET /admin-manager/analytics/order-heatmap/
      Returns placed orders bucketed by delivery area (city / rounded lat-lon),
      with order count and total revenue. Filterable by date range & status.

  GET /admin-manager/analytics/vendor-coverage-gaps/
      Cross-references areas where users/orders exist against vendor presence.
      Surfaces high-demand areas with zero or few active vendors — the whitespace
      opportunity map.

  GET /admin-manager/analytics/summary/
      Single-call summary card: totals used for top-level dashboard widgets.

All views require IsAuthenticated (admin JWT).
No new models are introduced — data is aggregated from:
  - account.Address  (user registration locations)
  - product.Order    (demand locations)
  - account.Vendor   (supply locations)
"""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Avg, Sum, Q, FloatField
from django.db.models.functions import Cast
from django.utils import timezone
from datetime import timedelta
import re

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from account.models import Address, User, Vendor
from product.models import DeliveryZone, Order
from helpers.response.response_format import success_response, bad_request_response, internal_server_error_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date_range(request):
    """
    Parse optional ?start_date=YYYY-MM-DD &end_date=YYYY-MM-DD query params.
    Falls back to last 90 days when not provided.
    Returns (start_dt, end_dt, error_response_or_None).
    """
    from datetime import datetime
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    now = timezone.now()

    try:
        start_dt = datetime.strptime(start_str, '%Y-%m-%d').replace(
            tzinfo=timezone.get_current_timezone()) if start_str else (now - timedelta(days=90))
        end_dt = datetime.strptime(end_str, '%Y-%m-%d').replace(
            tzinfo=timezone.get_current_timezone()) if end_str else now
    except ValueError:
        return None, None, bad_request_response(message='Invalid date format. Use YYYY-MM-DD.')

    return start_dt, end_dt, None


def _round_coord(value, precision=2):
    """Round a coordinate to 'precision' decimals for geo-bucketing."""
    try:
        return round(float(value), precision)
    except (TypeError, ValueError):
        return None


def _is_blank(value):
    return value is None or str(value).strip() == ''


def _zone_for_location(zones, latitude, longitude):
    if latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return None
    return next((zone for zone in zones if zone.contains_location(lat, lng)), None)


def _normalize_area_text(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()


def _zone_for_text(zones, *values):
    haystack = _normalize_area_text(' '.join(str(value or '') for value in values))
    if not haystack:
        return None

    for zone in zones:
        zone_name = _normalize_area_text(zone.name)
        primary_name = _normalize_area_text(zone.name.split('(')[0])
        bracket_matches = re.findall(r'\((.*?)\)', zone.name)
        aliases = [zone_name, primary_name] + [
            _normalize_area_text(alias)
            for alias in bracket_matches
        ]
        if any(alias and re.search(rf'\b{re.escape(alias)}\b', haystack) for alias in aliases):
            return zone
    return None


def _area_from_row(row, zones):
    zone = _zone_for_location(
        zones,
        row.get('delivery_latitude') or row.get('location_latitude'),
        row.get('delivery_longitude') or row.get('location_longitude'),
    )
    if not zone:
        zone = _zone_for_text(
            zones,
            row.get('address'),
            row.get('city'),
            row.get('state'),
            row.get('area_label'),
            row.get('name'),
        )
    if zone:
        return zone.name, 'Delivery Zone', zone.name

    city = (row.get('city') or '').strip()
    state = (row.get('state') or '').strip()
    if city and state:
        return city, state, f"{city}, {state}"
    if city:
        return city, '', city
    if state:
        return '', state, state
    return 'Unknown', 'Unknown', 'Unknown'


# ---------------------------------------------------------------------------
# 1. User Registration Locations
# ---------------------------------------------------------------------------

class AdminUserLocationAnalyticsView(generics.GenericAPIView):
    """
    GET /admin-manager/analytics/user-locations/

    Returns user registration locations grouped by area (city + state).
    Each group includes:
      - area label (city, state)
      - user_count
      - avg_lat / avg_lon  (centroid for map pin)
      - addresses with coordinates (for heatmap point cloud)

    Query params:
      state       – filter to a specific state (case-insensitive)
      city        – filter to a specific city (case-insensitive)
      start_date  – YYYY-MM-DD  (filters user created_at)
      end_date    – YYYY-MM-DD
      limit       – max groups to return (default 50)
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="User registration location analytics",
        operation_description=(
            "Returns customer registration locations grouped by city/state. "
            "Useful for identifying high-density areas without vendor coverage."
        ),
        manual_parameters=[
            openapi.Parameter('state', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='Filter by state name'),
            openapi.Parameter('city', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='Filter by city name'),
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='Start date YYYY-MM-DD (user registration date)'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='End date YYYY-MM-DD'),
            openapi.Parameter('limit', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description='Max number of area groups (default 50)'),
        ],
        responses={200: 'User location breakdown', 401: 'Unauthorized'},
    )
    def get(self, request):
        try:
            start_dt, end_dt, err = _parse_date_range(request)
            if err:
                return err

            state_filter = request.GET.get('state', '').strip()
            city_filter = request.GET.get('city', '').strip()
            limit = int(request.GET.get('limit', 50))

            # ── Filter users by registration date ──────────────────────────
            user_qs = User.objects.filter(
                role='buyer',
                created_at__gte=start_dt,
                created_at__lte=end_dt,
            )

            # ── Pull addresses linked to those users ───────────────────────
            addr_qs = Address.objects.filter(user__in=user_qs, is_active=True)

            if state_filter:
                addr_qs = addr_qs.filter(state__icontains=state_filter)
            if city_filter:
                addr_qs = addr_qs.filter(city__icontains=city_filter)

            zones = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))
            area_coord_map = {}

            def add_coord(key, row):
                lat = _round_coord(row.get('delivery_latitude') or row.get('location_latitude'), 5)
                lon = _round_coord(row.get('delivery_longitude') or row.get('location_longitude'), 5)
                if lat is None or lon is None:
                    return
                entry = area_coord_map.setdefault(key, {'lat_total': 0, 'lon_total': 0, 'coord_count': 0})
                entry['lat_total'] += lat
                entry['lon_total'] += lon
                entry['coord_count'] += 1

            def centroid_for(key):
                entry = area_coord_map.get(key)
                if not entry or not entry['coord_count']:
                    return None
                return {
                    'lat': _round_coord(entry['lat_total'] / entry['coord_count'], 5),
                    'lon': _round_coord(entry['lon_total'] / entry['coord_count'], 5),
                }
            area_map = {}
            for row in addr_qs.values(
                'user_id',
                'city',
                'state',
                'address',
                'location_latitude',
                'location_longitude',
            ):
                city, state, area_label = _area_from_row(row, zones)
                entry = area_map.setdefault(area_label, {
                    'city': city,
                    'state': state,
                    'area_label': area_label,
                    'user_ids': set(),
                    'address_count': 0,
                    'lat_total': 0,
                    'lon_total': 0,
                    'coord_count': 0,
                })
                entry['user_ids'].add(row['user_id'])
                entry['address_count'] += 1
                lat = _round_coord(row.get('location_latitude'), 5)
                lon = _round_coord(row.get('location_longitude'), 5)
                if lat is not None and lon is not None:
                    entry['lat_total'] += lat
                    entry['lon_total'] += lon
                    entry['coord_count'] += 1

            # ── Build heatmap point cloud (individual coords) ──────────────
            # Returns up to 500 individual geo-points for a dot-density map
            points_qs = addr_qs.exclude(
                location_latitude__isnull=True
            ).exclude(
                location_longitude__isnull=True
            ).values(
                'location_latitude', 'location_longitude', 'city', 'state', 'address'
            )[:500]

            points = [
                {
                    'lat': _round_coord(p['location_latitude'], 5),
                    'lon': _round_coord(p['location_longitude'], 5),
                    'city': _area_from_row(p, zones)[0],
                    'state': _area_from_row(p, zones)[1],
                    'area_label': _area_from_row(p, zones)[2],
                }
                for p in points_qs
                if _round_coord(p['location_latitude'], 5) is not None
            ]

            # ── Totals ─────────────────────────────────────────────────────
            total_users_in_range = user_qs.count()
            users_with_address = addr_qs.values('user').distinct().count()

            areas = sorted(
                area_map.values(),
                key=lambda item: len(item['user_ids']),
                reverse=True,
            )[:limit]
            for area in areas:
                coord_count = area.pop('coord_count')
                lat_total = area.pop('lat_total')
                lon_total = area.pop('lon_total')
                user_ids = area.pop('user_ids')
                area['user_count'] = len(user_ids)
                area['centroid'] = {
                    'lat': _round_coord(lat_total / coord_count, 5),
                    'lon': _round_coord(lon_total / coord_count, 5),
                } if coord_count else None

            return success_response(data={
                'period': {
                    'start_date': start_dt.date().isoformat(),
                    'end_date': end_dt.date().isoformat(),
                },
                'summary': {
                    'total_registered_users': total_users_in_range,
                    'users_with_saved_address': users_with_address,
                    'total_areas_found': len(areas),
                },
                'areas': areas,
                'heatmap_points': points,
            })

        except Exception as e:
            print(f"[AdminUserLocationAnalyticsView] Error: {e}")
            return internal_server_error_response()


# ---------------------------------------------------------------------------
# 2. Order Demand Heatmap
# ---------------------------------------------------------------------------

class AdminOrderHeatmapView(generics.GenericAPIView):
    """
    GET /admin-manager/analytics/order-heatmap/

    Returns placed orders grouped by delivery area (city + state).
    Each group includes order count, total revenue, and lat/lon centroid.

    Query params:
      state       – filter by state
      city        – filter by city
      start_date  – YYYY-MM-DD
      end_date    – YYYY-MM-DD
      status      – filter by order status (e.g. 'delivered')
      limit       – max groups (default 50)
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Order demand heatmap by area",
        operation_description=(
            "Returns order placement locations grouped by city/state. "
            "Shows where demand is highest so you can prioritise vendor onboarding."
        ),
        manual_parameters=[
            openapi.Parameter('state', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('city', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD'),
            openapi.Parameter('status', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='Order status to filter (e.g. delivered, pending)'),
            openapi.Parameter('limit', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description='Max areas to return (default 50)'),
        ],
        responses={200: 'Order demand heatmap', 401: 'Unauthorized'},
    )
    def get(self, request):
        try:
            start_dt, end_dt, err = _parse_date_range(request)
            if err:
                return err

            state_filter = request.GET.get('state', '').strip()
            city_filter = request.GET.get('city', '').strip()
            order_status = request.GET.get('status', '').strip()
            limit = int(request.GET.get('limit', 50))

            # ── Base queryset ──────────────────────────────────────────────
            order_qs = Order.objects.filter(
                created_at__gte=start_dt,
                created_at__lte=end_dt,
                payment_status='paid',
            )

            if state_filter:
                order_qs = order_qs.filter(state__icontains=state_filter)
            if city_filter:
                order_qs = order_qs.filter(city__icontains=city_filter)
            if order_status:
                order_qs = order_qs.filter(status=order_status)

            zones = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))
            area_map = {}
            area_rows = order_qs.values(
                'city',
                'state',
                'address',
                'location_latitude',
                'location_longitude',
                'delivery_latitude',
                'delivery_longitude',
                'total_amount',
            )
            for row in area_rows:
                city, state, area_label = _area_from_row(row, zones)
                entry = area_map.setdefault(area_label, {
                    'city': city,
                    'state': state,
                    'area_label': area_label,
                    'order_count': 0,
                    'total_revenue': 0,
                    'lat_total': 0,
                    'lon_total': 0,
                    'coord_count': 0,
                })
                entry['order_count'] += 1
                entry['total_revenue'] += float(row['total_amount'] or 0)
                lat = _round_coord(row.get('delivery_latitude') or row.get('location_latitude'), 5)
                lon = _round_coord(row.get('delivery_longitude') or row.get('location_longitude'), 5)
                if lat is not None and lon is not None:
                    entry['lat_total'] += lat
                    entry['lon_total'] += lon
                    entry['coord_count'] += 1

            # ── Point cloud for map (up to 500 individual delivery coords) ─
            points_qs = order_qs.exclude(
                Q(location_latitude__isnull=True) & Q(delivery_latitude__isnull=True)
            ).exclude(
                Q(location_longitude__isnull=True) & Q(delivery_longitude__isnull=True)
            ).values(
                'location_latitude',
                'location_longitude',
                'delivery_latitude',
                'delivery_longitude',
                'city',
                'state',
                'address',
                'total_amount'
            )[:500]

            points = [
                {
                    'lat': _round_coord(p.get('delivery_latitude') or p.get('location_latitude'), 5),
                    'lon': _round_coord(p.get('delivery_longitude') or p.get('location_longitude'), 5),
                    'city': _area_from_row(p, zones)[0],
                    'state': _area_from_row(p, zones)[1],
                    'area_label': _area_from_row(p, zones)[2],
                    'order_value': float(p['total_amount'] or 0),
                }
                for p in points_qs
                if _round_coord(p.get('delivery_latitude') or p.get('location_latitude'), 5) is not None
            ]

            # ── Totals ─────────────────────────────────────────────────────
            totals = order_qs.aggregate(
                total_orders=Count('id'),
                total_revenue=Sum('total_amount'),
            )

            areas = sorted(
                area_map.values(),
                key=lambda item: item['order_count'],
                reverse=True,
            )[:limit]
            for area in areas:
                coord_count = area.pop('coord_count')
                lat_total = area.pop('lat_total')
                lon_total = area.pop('lon_total')
                area['centroid'] = {
                    'lat': _round_coord(lat_total / coord_count, 5),
                    'lon': _round_coord(lon_total / coord_count, 5),
                } if coord_count else None

            return success_response(data={
                'period': {
                    'start_date': start_dt.date().isoformat(),
                    'end_date': end_dt.date().isoformat(),
                },
                'summary': {
                    'total_orders': totals['total_orders'] or 0,
                    'total_revenue': float(totals['total_revenue'] or 0),
                    'total_areas_found': len(areas),
                },
                'areas': areas,
                'heatmap_points': points,
            })

        except Exception as e:
            print(f"[AdminOrderHeatmapView] Error: {e}")
            return internal_server_error_response()


# ---------------------------------------------------------------------------
# 3. Vendor Coverage Gaps
# ---------------------------------------------------------------------------

class AdminVendorCoverageGapView(generics.GenericAPIView):
    """
    GET /admin-manager/analytics/vendor-coverage-gaps/

    Cross-references demand areas (from orders + user addresses) against
    vendor supply. Returns:
      - Areas with HIGH demand and ZERO vendors  → top priority for onboarding
      - Areas with HIGH demand and FEW vendors   → growth opportunity
      - Areas with vendors but LOW/ZERO orders   → underperforming coverage

    Query params:
      start_date     – lookback window start (default: last 90 days)
      end_date
      min_users      – minimum user count to flag an area (default 5)
      min_orders     – minimum order count to flag an area (default 3)
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Vendor coverage gap analysis",
        operation_description=(
            "Identifies areas with high customer density or order demand "
            "but zero or very few active vendors. Guides onboarding & marketing decisions."
        ),
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD (default: 90 days ago)'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD'),
            openapi.Parameter('min_users', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description='Min user count to include an area (default 5)'),
            openapi.Parameter('min_orders', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description='Min order count to include an area (default 3)'),
        ],
        responses={200: 'Coverage gap analysis', 401: 'Unauthorized'},
    )
    def get(self, request):
        try:
            start_dt, end_dt, err = _parse_date_range(request)
            if err:
                return err

            min_users = int(request.GET.get('min_users', 5))
            min_orders = int(request.GET.get('min_orders', 3))

            zones = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))

            # ── Users per zone/area ────────────────────────────────────────
            user_area_sets = {}
            for row in Address.objects.filter(
                user__role='buyer',
                user__created_at__gte=start_dt,
                user__created_at__lte=end_dt,
                is_active=True,
            ).values('user_id', 'city', 'state', 'address', 'location_latitude', 'location_longitude'):
                city, state, _area_label = _area_from_row(row, zones)
                key = (city, state)
                user_area_sets.setdefault(key, set()).add(row['user_id'])
                add_coord(key, row)
            user_area_map = {
                key: len(user_ids)
                for key, user_ids in user_area_sets.items()
            }

            # ── Orders per area. Prefer delivery zone, fall back to city/state. ──
            order_area_map = {}
            for row in Order.objects.filter(
                created_at__gte=start_dt,
                created_at__lte=end_dt,
                payment_status='paid',
            ).values(
                'city',
                'state',
                'address',
                'location_latitude',
                'location_longitude',
                'delivery_latitude',
                'delivery_longitude',
                'total_amount',
            ):
                city, state, _area_label = _area_from_row(row, zones)
                key = (city, state)
                entry = order_area_map.setdefault(key, {
                    'order_count': 0,
                    'total_revenue': 0,
                })
                entry['order_count'] += 1
                entry['total_revenue'] += float(row['total_amount'] or 0)
                add_coord(key, row)

            # ── Active vendors per zone/area ───────────────────────────────
            vendor_area_map = {}
            for row in Vendor.objects.filter(
                is_active=True,
                approval_status='approved',
            ).values('id', 'name', 'city', 'state', 'address', 'location_latitude', 'location_longitude'):
                city, state, _area_label = _area_from_row(row, zones)
                key = (city, state)
                vendor_area_map[key] = vendor_area_map.get(key, 0) + 1
                add_coord(key, row)

            # ── Merge all areas ────────────────────────────────────────────
            all_area_keys = set(user_area_map) | set(order_area_map) | set(vendor_area_map)

            no_vendor_areas = []      # 0 vendors, high demand
            low_vendor_areas = []     # 1-2 vendors, notable demand
            underserved_areas = []    # vendors exist but almost no orders

            for city, state in all_area_keys:
                if city == 'Unknown' and state == 'Unknown':
                    continue
                key = (city, state)
                users = user_area_map.get(key, 0)
                orders_info = order_area_map.get(key, {'order_count': 0, 'total_revenue': 0})
                vendors = vendor_area_map.get(key, 0)

                order_count = orders_info['order_count']
                revenue = orders_info['total_revenue']
                area_label = city if state == 'Delivery Zone' else f"{city or 'Unknown'}, {state or 'Unknown'}"

                entry = {
                    'city': city or 'Unknown',
                    'state': state or 'Unknown',
                    'area_label': area_label,
                    'user_count': users,
                    'order_count': order_count,
                    'total_revenue': revenue,
                    'vendor_count': vendors,
                    'demand_score': users + (order_count * 2),  # weighted signal
                    'centroid': centroid_for(key),
                }

                if vendors == 0 and (users >= min_users or order_count >= min_orders):
                    no_vendor_areas.append(entry)
                elif 1 <= vendors <= 2 and (users >= min_users or order_count >= min_orders):
                    low_vendor_areas.append(entry)
                elif vendors >= 1 and order_count == 0:
                    underserved_areas.append(entry)

            # Sort by demand score descending
            no_vendor_areas.sort(key=lambda x: x['demand_score'], reverse=True)
            low_vendor_areas.sort(key=lambda x: x['demand_score'], reverse=True)
            underserved_areas.sort(key=lambda x: x['vendor_count'], reverse=True)

            # ── All vendors map (for context) ──────────────────────────────
            all_vendor_areas = [
                {
                    'city': city or 'Unknown',
                    'state': state or 'Unknown',
                    'area_label': city if state == 'Delivery Zone' else f"{city or 'Unknown'}, {state or 'Unknown'}",
                    'vendor_count': vendor_count,
                    'centroid': centroid_for((city, state)),
                }
                for (city, state), vendor_count in vendor_area_map.items()
            ]

            return success_response(data={
                'period': {
                    'start_date': start_dt.date().isoformat(),
                    'end_date': end_dt.date().isoformat(),
                },
                'summary': {
                    'total_areas_with_users': len(user_area_map),
                    'total_areas_with_orders': len(order_area_map),
                    'total_areas_with_vendors': len(vendor_area_map),
                    'high_demand_no_vendor': len(no_vendor_areas),
                    'high_demand_low_vendor': len(low_vendor_areas),
                    'vendor_present_no_orders': len(underserved_areas),
                },
                'high_demand_no_vendor': no_vendor_areas,
                'high_demand_low_vendor': low_vendor_areas,
                'underserved_vendor_areas': underserved_areas,
                'all_vendor_coverage': all_vendor_areas,
            })

        except Exception as e:
            print(f"[AdminVendorCoverageGapView] Error: {e}")
            return internal_server_error_response()


# ---------------------------------------------------------------------------
# 4. Summary Dashboard Card
# ---------------------------------------------------------------------------

class AdminLocationSummaryView(generics.GenericAPIView):
    """
    GET /admin-manager/analytics/summary/

    Single-call summary of all location analytics for dashboard widget cards.
    Returns top-line numbers without full breakdown arrays, fast to load.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Location analytics summary (dashboard cards)",
        operation_description=(
            "Returns aggregated location intelligence metrics for the admin "
            "dashboard overview — total users per top city, top demand area, "
            "number of gap areas, etc."
        ),
        responses={200: 'Summary analytics', 401: 'Unauthorized'},
    )
    def get(self, request):
        try:
            # Last 30 days default for summary
            now = timezone.now()
            start_dt = now - timedelta(days=30)

            zones = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))

            # Top 5 signup zones. Prefer delivery zone, fall back to city/state.
            user_area_counts = {}
            for row in Address.objects.filter(
                user__role='buyer',
                is_active=True,
            ).values('user_id', 'city', 'state', 'address', 'location_latitude', 'location_longitude'):
                city, state, area_label = _area_from_row(row, zones)
                entry = user_area_counts.setdefault(area_label, {
                    'city': city,
                    'state': state,
                    'area_label': area_label,
                    'user_ids': set(),
                })
                entry['user_ids'].add(row['user_id'])
            top_user_cities = sorted(
                (
                    {
                        'area_label': item['area_label'],
                        'user_count': len(item['user_ids']),
                    }
                    for item in user_area_counts.values()
                ),
                key=lambda item: item['user_count'],
                reverse=True,
            )[:5]

            # Top 5 order areas by order count. Prefer city/state, fall back to delivery zone.
            order_area_counts = {}
            for row in Order.objects.filter(
                created_at__gte=start_dt,
                payment_status='paid',
            ).values(
                'city',
                'state',
                'address',
                'location_latitude',
                'location_longitude',
                'delivery_latitude',
                'delivery_longitude',
            ):
                city, state, area_label = _area_from_row(row, zones)
                entry = order_area_counts.setdefault(area_label, {
                    'city': city,
                    'state': state,
                    'area_label': area_label,
                    'order_count': 0,
                })
                entry['order_count'] += 1
            top_order_cities = sorted(
                order_area_counts.values(),
                key=lambda item: item['order_count'],
                reverse=True,
            )[:5]

            # Count of cities with demand but no vendor
            cities_with_demand = {
                (item['city'], item['state'])
                for item in order_area_counts.values()
            }
            cities_with_vendors = set(
                _area_from_row(r, zones)[:2]
                for r in Vendor.objects.filter(
                    is_active=True, approval_status='approved'
                ).values('name', 'city', 'state', 'address', 'location_latitude', 'location_longitude')
            )
            gap_count = len(cities_with_demand - cities_with_vendors)

            # New signups in last 30 days
            new_users_30d = User.objects.filter(
                role='buyer', created_at__gte=start_dt
            ).count()

            return success_response(data={
                'period_days': 30,
                'new_users_last_30_days': new_users_30d,
                'gap_areas_count': gap_count,
                'top_cities_by_users': [
                    {
                        'area_label': r['area_label'],
                        'user_count': r['user_count'],
                    }
                    for r in top_user_cities
                ],
                'top_cities_by_orders': [
                    {
                        'area_label': r['area_label'],
                        'order_count': r['order_count'],
                    }
                    for r in top_order_cities
                ],
            })

        except Exception as e:
            print(f"[AdminLocationSummaryView] Error: {e}")
            return internal_server_error_response()
