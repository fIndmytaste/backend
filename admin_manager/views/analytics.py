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

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from account.models import Address, User, Vendor
from product.models import Order
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

            # ── Group by city + state ──────────────────────────────────────
            grouped = (
                addr_qs
                .values('city', 'state')
                .annotate(
                    user_count=Count('user', distinct=True),
                    address_count=Count('id'),
                    avg_lat=Avg(Cast('location_latitude', output_field=FloatField())),
                    avg_lon=Avg(Cast('location_longitude', output_field=FloatField())),
                )
                .order_by('-user_count')[:limit]
            )

            # ── Build heatmap point cloud (individual coords) ──────────────
            # Returns up to 500 individual geo-points for a dot-density map
            points_qs = addr_qs.exclude(
                location_latitude__isnull=True
            ).exclude(
                location_longitude__isnull=True
            ).values(
                'location_latitude', 'location_longitude', 'city', 'state'
            )[:500]

            points = [
                {
                    'lat': _round_coord(p['location_latitude'], 5),
                    'lon': _round_coord(p['location_longitude'], 5),
                    'city': p['city'],
                    'state': p['state'],
                }
                for p in points_qs
                if _round_coord(p['location_latitude'], 5) is not None
            ]

            # ── Totals ─────────────────────────────────────────────────────
            total_users_in_range = user_qs.count()
            users_with_address = addr_qs.values('user').distinct().count()

            areas = [
                {
                    'city': g['city'] or 'Unknown',
                    'state': g['state'] or 'Unknown',
                    'area_label': f"{g['city'] or 'Unknown'}, {g['state'] or 'Unknown'}",
                    'user_count': g['user_count'],
                    'address_count': g['address_count'],
                    'centroid': {
                        'lat': _round_coord(g['avg_lat'], 5),
                        'lon': _round_coord(g['avg_lon'], 5),
                    } if g['avg_lat'] and g['avg_lon'] else None,
                }
                for g in grouped
            ]

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

            # ── Group by city + state ──────────────────────────────────────
            grouped = (
                order_qs
                .values('city', 'state')
                .annotate(
                    order_count=Count('id'),
                    total_revenue=Sum('total_amount'),
                    avg_lat=Avg(Cast('location_latitude', output_field=FloatField())),
                    avg_lon=Avg(Cast('location_longitude', output_field=FloatField())),
                )
                .order_by('-order_count')[:limit]
            )

            # ── Point cloud for map (up to 500 individual delivery coords) ─
            points_qs = order_qs.exclude(
                location_latitude__isnull=True
            ).exclude(
                location_longitude__isnull=True
            ).values(
                'location_latitude', 'location_longitude', 'city', 'state', 'total_amount'
            )[:500]

            points = [
                {
                    'lat': _round_coord(p['location_latitude'], 5),
                    'lon': _round_coord(p['location_longitude'], 5),
                    'city': p['city'],
                    'state': p['state'],
                    'order_value': float(p['total_amount'] or 0),
                }
                for p in points_qs
                if _round_coord(p['location_latitude'], 5) is not None
            ]

            # ── Totals ─────────────────────────────────────────────────────
            totals = order_qs.aggregate(
                total_orders=Count('id'),
                total_revenue=Sum('total_amount'),
            )

            areas = [
                {
                    'city': g['city'] or 'Unknown',
                    'state': g['state'] or 'Unknown',
                    'area_label': f"{g['city'] or 'Unknown'}, {g['state'] or 'Unknown'}",
                    'order_count': g['order_count'],
                    'total_revenue': float(g['total_revenue'] or 0),
                    'centroid': {
                        'lat': _round_coord(g['avg_lat'], 5),
                        'lon': _round_coord(g['avg_lon'], 5),
                    } if g['avg_lat'] and g['avg_lon'] else None,
                }
                for g in grouped
            ]

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

            # ── Users per city/state ───────────────────────────────────────
            user_areas = (
                Address.objects.filter(
                    user__role='buyer',
                    user__created_at__gte=start_dt,
                    user__created_at__lte=end_dt,
                    is_active=True,
                )
                .values('city', 'state')
                .annotate(user_count=Count('user', distinct=True))
            )
            user_area_map = {
                (r['city'] or '', r['state'] or ''): r['user_count']
                for r in user_areas
            }

            # ── Orders per city/state ──────────────────────────────────────
            order_areas = (
                Order.objects.filter(
                    created_at__gte=start_dt,
                    created_at__lte=end_dt,
                    payment_status='paid',
                )
                .values('city', 'state')
                .annotate(
                    order_count=Count('id'),
                    total_revenue=Sum('total_amount'),
                )
            )
            order_area_map = {
                (r['city'] or '', r['state'] or ''): {
                    'order_count': r['order_count'],
                    'total_revenue': float(r['total_revenue'] or 0),
                }
                for r in order_areas
            }

            # ── Active vendors per city/state ──────────────────────────────
            vendor_areas = (
                Vendor.objects.filter(is_active=True, approval_status='approved')
                .values('city', 'state')
                .annotate(vendor_count=Count('id'))
            )
            vendor_area_map = {
                (r['city'] or '', r['state'] or ''): r['vendor_count']
                for r in vendor_areas
            }

            # ── Merge all areas ────────────────────────────────────────────
            all_area_keys = set(user_area_map) | set(order_area_map) | set(vendor_area_map)

            no_vendor_areas = []      # 0 vendors, high demand
            low_vendor_areas = []     # 1-2 vendors, notable demand
            underserved_areas = []    # vendors exist but almost no orders

            for city, state in all_area_keys:
                key = (city, state)
                users = user_area_map.get(key, 0)
                orders_info = order_area_map.get(key, {'order_count': 0, 'total_revenue': 0})
                vendors = vendor_area_map.get(key, 0)

                order_count = orders_info['order_count']
                revenue = orders_info['total_revenue']
                area_label = f"{city or 'Unknown'}, {state or 'Unknown'}"

                entry = {
                    'city': city or 'Unknown',
                    'state': state or 'Unknown',
                    'area_label': area_label,
                    'user_count': users,
                    'order_count': order_count,
                    'total_revenue': revenue,
                    'vendor_count': vendors,
                    'demand_score': users + (order_count * 2),  # weighted signal
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
                    'city': r['city'] or 'Unknown',
                    'state': r['state'] or 'Unknown',
                    'area_label': f"{r['city'] or 'Unknown'}, {r['state'] or 'Unknown'}",
                    'vendor_count': r['vendor_count'],
                }
                for r in vendor_areas
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

            # Top 5 cities by user registration
            top_user_cities = (
                Address.objects.filter(
                    user__role='buyer',
                    is_active=True,
                )
                .values('city', 'state')
                .annotate(user_count=Count('user', distinct=True))
                .order_by('-user_count')[:5]
            )

            # Top 5 cities by order count (last 30 days)
            top_order_cities = (
                Order.objects.filter(
                    created_at__gte=start_dt,
                    payment_status='paid',
                )
                .values('city', 'state')
                .annotate(order_count=Count('id'))
                .order_by('-order_count')[:5]
            )

            # Count of cities with demand but no vendor
            cities_with_demand = set(
                (r['city'] or '', r['state'] or '')
                for r in Order.objects.filter(
                    created_at__gte=start_dt,
                    payment_status='paid',
                ).values('city', 'state').distinct()
            )
            cities_with_vendors = set(
                (r['city'] or '', r['state'] or '')
                for r in Vendor.objects.filter(
                    is_active=True, approval_status='approved'
                ).values('city', 'state').distinct()
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
                        'area_label': f"{r['city'] or 'Unknown'}, {r['state'] or 'Unknown'}",
                        'user_count': r['user_count'],
                    }
                    for r in top_user_cities
                ],
                'top_cities_by_orders': [
                    {
                        'area_label': f"{r['city'] or 'Unknown'}, {r['state'] or 'Unknown'}",
                        'order_count': r['order_count'],
                    }
                    for r in top_order_cities
                ],
            })

        except Exception as e:
            print(f"[AdminLocationSummaryView] Error: {e}")
            return internal_server_error_response()
