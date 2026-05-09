from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg, Case, IntegerField, Sum, Count, Q, Value, When
from django.utils import timezone
from datetime import timedelta
from uuid import UUID

from account.models import Rider, User, Vendor
from account.serializers import RiderSerializer
from admin_manager.serializers.products import AdminProductCategoriesSerializer
from helpers.response.response_format import paginate_success_response_with_serializer, success_response,bad_request_response
from product.models import DeliveryZone, Order, Product, Rating, SystemCategory
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi 

from product.serializers import AdminOrderListSerializer, OrderSerializer, RatingSerializer
from vendor.serializers import ProductSerializer


def _is_uuid(value):
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


class AdminSystemCategoryListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminProductCategoriesSerializer

    @swagger_auto_schema(
        operation_description="Get a list of all system categories.",
        operation_summary="Retrieve a list of all system categories.",
        responses={
            200: AdminProductCategoriesSerializer(many=True),
            401: "Unauthorized",
        }
    )
    def get(self, request):
        categories = SystemCategory.objects.all()
        serializer = self.serializer_class(categories, many=True)
        return success_response(serializer.data)


class AdminDeliveryZoneListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        zones = DeliveryZone.objects.filter(is_active=True).order_by('name')
        return success_response([
            {
                "id": str(zone.id),
                "name": zone.name,
                "fixed_fee": float(zone.fixed_fee),
            }
            for zone in zones
        ])




class AdminProductBySystemCategoryView(generics.GenericAPIView):
    """
    Endpoint to get products by system category.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer

    @swagger_auto_schema(
        operation_description="Get a list of products belonging to a system category.",
        operation_summary="Retrieve products by system category.",
        responses={
            200: ProductSerializer(many=True),
            400: "Bad Request",
            401: "Unauthorized",
        },
        parameters=[
            {
                'name': 'system_category_id',
                'description': 'The ID of the system category to filter products by.',
                'required': True,
                'type': 'integer',
            }
        ]
    )
    def get(self, request, system_category_id):
        products = Product.objects.filter(parent=None,system_category_id=system_category_id,context={'request': request})
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            products,
            page_size=int(request.GET.get('page_size',20))
        )
    


class AdminProductDetailView(generics.GenericAPIView):
    serializer_class = ProductSerializer
    permission_classes = []
    # permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get the details of a product.",
        operation_summary="Retrieve the details of a specific product.",
        responses={
            200: ProductSerializer,
            404: "Product Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, product_id):
        product = Product.objects.get(id=product_id)
        serializer = self.serializer_class(product,context={'request': request})
        return success_response(serializer.data)




class AdminProductRatingListView(generics.ListAPIView):
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    
    def get_queryset(self):
        product_id = self.kwargs['product_id']
        try:
            product = Product.objects.get(id=product_id)
            return Rating.objects.filter(product=product)
        except Product.DoesNotExist:
            return Rating.objects.none()  
        
    @swagger_auto_schema(
        operation_description="Get all ratings for a specific product.",
        operation_summary="Retrieve ratings for a product.",
        responses={
            200: RatingSerializer(many=True),
            404: "Product not found.",
            401: "Authentication required."
        }
    )
    def get(self,request,*args,**kwargs):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            page_size=int(request.GET.get('page_size',20))
        )




class AdminDashboardOverviewAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    # Statuses that mean an order is actively being processed (not yet done, not cancelled)
    ACTIVE_ORDER_STATUSES = [
        'pending', 'confirmed', 'preparing',
        'looking_for_rider', 'rider_assigned',
        'picked_up', 'in_transit', 'near_delivery',
    ]

    @swagger_auto_schema(
        operation_summary="Admin Dashboard Overview",
        operation_description="Get dashboard metrics (orders, users, earnings, payouts) for a specific time range.",
        manual_parameters=[
            openapi.Parameter(
                'time_range',
                openapi.IN_QUERY,
                description="Time range filter (week, month, year). Defaults to 'week'.",
                type=openapi.TYPE_STRING,
                enum=['week', 'month', 'year'],
                required=False
            )
        ],
        responses={200: "Dashboard metrics", 401: "Unauthorized"}
    )
    def get(self, request):
        time_range = request.query_params.get('time_range', 'week')

        today = timezone.now()
        if time_range == 'month':
            delta = timedelta(days=30)
        elif time_range == 'year':
            delta = timedelta(days=365)
        else:
            delta = timedelta(days=7)

        start_date = today - delta
        prev_start = start_date - delta

        # ── Orders ──────────────────────────────────────────────────────────
        base_orders = Order.objects.filter(created_at__gte=start_date)

        completed_statuses = ['delivered']
        canceled_statuses = ['canceled', 'cancelled', 'rejected', 'failed', 'payment_failed']

        order_agg = base_orders.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status__in=self.ACTIVE_ORDER_STATUSES)),
            completed=Count('id', filter=Q(status__in=completed_statuses) | Q(delivery_status__in=completed_statuses)),
            canceled=Count('id', filter=Q(status__in=canceled_statuses) | Q(delivery_status__in=canceled_statuses)),
        )

        # ── Revenue: use real vendor_amount field, fall back to sum of total_amount ──
        revenue_agg = base_orders.filter(payment_status='paid').aggregate(
            total_earnings=Sum('total_amount'),
            vendor_payouts=Sum('vendor_amount'),
            platform_earnings=Sum('platform_amount'),
        )
        total_earnings = revenue_agg['total_earnings'] or 0
        vendor_payouts = revenue_agg['vendor_payouts'] or 0

        # ── Previous period for growth indicators ───────────────────────────
        prev_orders = Order.objects.filter(
            created_at__gte=prev_start,
            created_at__lt=start_date,
        )
        prev_total = prev_orders.count()
        prev_earnings = prev_orders.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        order_growth = order_agg['total'] > 0 if prev_total == 0 else (order_agg['total'] > prev_total)
        earnings_growth = total_earnings > 0 if float(prev_earnings) == 0 else (float(total_earnings) > float(prev_earnings))

        # ── Users ────────────────────────────────────────────────────────────
        total_users = User.objects.count()
        total_customers = User.objects.filter(role='buyer').count()

        active_users = User.objects.filter(is_active=True, last_login__gte=start_date).count()
        new_users = User.objects.filter(created_at__gte=start_date).count()
        vendors_count = Vendor.objects.count()
        riders_count = Rider.objects.count()

        prev_active_users = User.objects.filter(
            is_active=True,
            last_login__gte=prev_start,
            last_login__lt=start_date,
        ).count()
        user_growth = active_users > 0 if prev_active_users == 0 else (active_users > prev_active_users)

        return success_response(data={
            "order_overview": {
                "total_orders": {"value": order_agg['total'], "growth": order_growth},
                "active_orders": {"value": order_agg['active']},
                "completed_orders": {"value": order_agg['completed']},
                "canceled_orders": {"value": order_agg['canceled']},
            },
            "revenue_summary": {
                "total_earnings": {"value": float(total_earnings), "growth": earnings_growth},
                "vendor_payouts": {"value": float(vendor_payouts)},
                "platform_earnings": {"value": float(revenue_agg['platform_earnings'] or 0)},
            },
            "user_metrics": {
                "total_users": {"value": total_users},
                "total_customers": {"value": total_customers},
                "customers": {"value": total_customers},
                "active_users": {"value": active_users, "growth": user_growth},
                "new_users": {"value": new_users},
                "vendors": {"value": vendors_count},
                "riders": {"value": riders_count},
            }
        })



class AdminGetMarketPlaceRiderListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderSerializer
    queryset = Rider.objects.filter(is_in_house_rider=True).select_related('user')


    def _zone_for_location(self, zones, latitude, longitude):
        if latitude is None or longitude is None:
            return None
        try:
            lat = float(latitude)
            lng = float(longitude)
        except (TypeError, ValueError):
            return None
        return next((zone for zone in zones if zone.contains_location(lat, lng)), None)

    def get(self,request):
        order = None
        order_id = request.GET.get('order_id')
        zone_id = request.GET.get('zone_id')
        queryset = self.get_queryset().filter(
            status='active',
            is_verified=True,
        ).annotate(
            ongoing_orders_count=Count(
                'orders',
                filter=Q(orders__status__in=[
                    'rider_assigned',
                    'confirmed',
                    'preparing',
                    'picked_up',
                    'in_transit',
                    'near_delivery',
                ]),
                distinct=True,
            )
        ).annotate(
            overall_rating=Avg('ratings__rating'),
        ).order_by('ongoing_orders_count', '-created_at')
        zones = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))
        order_zone = None

        if zone_id:
            order_zone = next((zone for zone in zones if str(zone.id) == str(zone_id)), None)
            if not order_zone:
                return bad_request_response(message="Delivery zone not found.", status_code=404)

        if order_id:
            try:
                order = Order.objects.only(
                    'id',
                    'delivery_latitude',
                    'delivery_longitude',
                    'location_latitude',
                    'location_longitude',
                ).get(id=order_id)
            except Order.DoesNotExist:
                return bad_request_response(message="Order not found.", status_code=404)

            if not order_zone:
                latitude = order.delivery_latitude or order.location_latitude
                longitude = order.delivery_longitude or order.location_longitude
                order_zone = self._zone_for_location(zones, latitude, longitude)

        if order_zone:
            matching_ids = [
                rider.id
                for rider in queryset
                if self._zone_for_location(
                    zones,
                    rider.current_latitude or rider.location_latitude,
                    rider.current_longitude or rider.location_longitude,
                ) == order_zone
            ]
            queryset = queryset.filter(id__in=matching_ids)

        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            queryset,
            page_size=int(request.GET.get('page_size',20)),
            addition_serializer_data={
                "rider_type":'marketplace',
                "marketplace_order": order,
            },
            extra_serializer_context={
                "active_delivery_zones": zones,
                "assignment_order_zone": order_zone,
            },
        )
    


class AdminGetMarketPlaceVendorOrdersAPIView(generics.GenericAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all().order_by('-created_at')


    def get_queryset(self,vendor_id):
        queryset = Order.objects.filter(vendor__id=vendor_id).order_by('-created_at')
        track_id = self.request.GET.get('track_id')
        status = self.request.GET.get('status')

        

        if track_id:
            queryset = queryset.filter(track_id__icontains=track_id)

        if status:
            queryset = queryset.filter(status__iexact=status)

        return queryset

    @swagger_auto_schema(
        operation_summary="List All Orders (Admin)",
        operation_description="Retrieve a paginated list of all orders. Supports filtering by track ID and order status.",
        manual_parameters=[
            openapi.Parameter(
                'track_id',
                openapi.IN_QUERY,
                description="Search orders by tracking ID (partial match allowed)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Filter orders by status (e.g., pending, shipped, delivered, canceled)",
                type=openapi.TYPE_STRING,
                enum=['pending', 'shipped', 'delivered', 'canceled'],
                required=False
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of orders to return per page",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of orders",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "data": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                description="Order object (serialized)",
                            )
                        )
                    }
                )
            ),
            401: "Unauthorized"
        }
    )
    def get(self,request,vendor_id):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(vendor_id),
            page_size=int(request.GET.get('page_size',20))
        )





class AdminGetAllOrdersAPIView(generics.GenericAPIView):
    serializer_class = AdminOrderListSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all().select_related(
        'user',
        'vendor',
        'vendor__user',
        'vendor__category',
        'rider',
        'rider__user',
    ).prefetch_related('vendor__marketplace_set').order_by('-created_at')


    def get_queryset(self):
        queryset = super().get_queryset()
        track_id = self.request.GET.get('track_id')
        search = self.request.GET.get('search')
        status = self.request.GET.get('status')
        category = self.request.GET.get('category') or self.request.GET.get('category_id')
        marketplace = self.request.GET.get('marketplace') or self.request.GET.get('marketplace_id')

        if track_id:
            queryset = queryset.filter(track_id__icontains=track_id)

        if search:
            queryset = queryset.filter(
                Q(track_id__icontains=search) |
                Q(id__icontains=search) |
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(vendor__name__icontains=search) |
                Q(vendor__email__icontains=search) |
                Q(vendor__category__name__icontains=search) |
                Q(vendor__marketplace__name__icontains=search) |
                Q(address__icontains=search)
            ).distinct()

        if status:
            queryset = queryset.filter(status__iexact=status)

        if category:
            category_filter = Q(vendor__category__name__icontains=category)
            if _is_uuid(category):
                category_filter |= Q(vendor__category_id=category)
            queryset = queryset.filter(category_filter)

        if marketplace:
            marketplace_filter = Q(vendor__marketplace__name__icontains=marketplace)
            if _is_uuid(marketplace):
                marketplace_filter |= Q(vendor__marketplace__id=marketplace)
            queryset = queryset.filter(marketplace_filter).distinct()

        return queryset

    @swagger_auto_schema(
        operation_summary="List All Orders (Admin)",
        operation_description="Retrieve a paginated list of all orders. Supports filtering by track ID and order status.",
        manual_parameters=[
            openapi.Parameter(
                'track_id',
                openapi.IN_QUERY,
                description="Search orders by tracking ID (partial match allowed)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Filter orders by status (e.g., pending, shipped, delivered, canceled)",
                type=openapi.TYPE_STRING,
                enum=['pending', 'shipped', 'delivered', 'canceled'],
                required=False
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of orders to return per page",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of orders",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "data": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                description="Order object (serialized)",
                            )
                        )
                    }
                )
            ),
            401: "Unauthorized"
        }
    )
    def get(self,request):
        addition_serializer_data = {
            'is_vendor':True
        }
        active_delivery_zones = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            page_size=int(request.GET.get('page_size',20)),
            addition_serializer_data=addition_serializer_data,
            extra_serializer_context={'active_delivery_zones': active_delivery_zones}
        )
    


class AdminGetAllMarketPlaceVendorOrdersAPIView(generics.GenericAPIView):
    """
    Endpoint to fetch all orders from all marketplace vendors.
    """
    serializer_class = AdminOrderListSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.filter(
        Q(vendor__is_marketplace=True) | Q(vendor__marketplace__isnull=False)
    ).distinct().order_by('-created_at')

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'user',
            'vendor',
            'vendor__user',
            'vendor__category',
            'rider',
            'rider__user',
        ).prefetch_related('vendor__marketplace_set')
        track_id = self.request.GET.get('track_id')
        search = self.request.GET.get('search')
        status = self.request.GET.get('status')
        assignment_status = self.request.GET.get('assignment_status')
        vendor_id = self.request.GET.get('vendor_id')
        zone_id = self.request.GET.get('zone_id')
        category = self.request.GET.get('category') or self.request.GET.get('category_id')
        marketplace = self.request.GET.get('marketplace') or self.request.GET.get('marketplace_id')

        if track_id:
            queryset = queryset.filter(track_id__icontains=track_id)

        if search:
            queryset = queryset.filter(
                Q(track_id__icontains=search) |
                Q(id__icontains=search) |
                Q(vendor__name__icontains=search) |
                Q(vendor__email__icontains=search) |
                Q(vendor__category__name__icontains=search) |
                Q(vendor__marketplace__name__icontains=search) |
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search)
            ).distinct()

        if status:
            queryset = queryset.filter(status__iexact=status)

        if assignment_status == 'incoming':
            queryset = queryset.filter(rider__isnull=True).exclude(
                Q(status__in=['delivered', 'canceled', 'rejected', 'failed', 'payment_failed']) |
                Q(delivery_status__in=['delivered', 'canceled'])
            )
        elif assignment_status == 'assigned':
            queryset = queryset.filter(rider__isnull=False).exclude(
                Q(status__in=['delivered', 'canceled', 'rejected', 'failed', 'payment_failed']) |
                Q(delivery_status__in=['delivered', 'canceled'])
            )
        elif assignment_status == 'completed':
            queryset = queryset.filter(Q(status='delivered') | Q(delivery_status='delivered'))
        elif assignment_status in ['canceled', 'cancelled']:
            queryset = queryset.filter(
                Q(status__in=['canceled', 'rejected', 'failed', 'payment_failed']) |
                Q(delivery_status='canceled')
            )
        
        if vendor_id:
            queryset = queryset.filter(vendor__id=vendor_id)

        if category:
            category_filter = Q(vendor__category__name__icontains=category)
            if _is_uuid(category):
                category_filter |= Q(vendor__category_id=category)
            queryset = queryset.filter(category_filter)

        if marketplace:
            marketplace_filter = Q(vendor__marketplace__name__icontains=marketplace)
            if _is_uuid(marketplace):
                marketplace_filter |= Q(vendor__marketplace__id=marketplace)
            queryset = queryset.filter(marketplace_filter).distinct()

        if zone_id:
            try:
                zones = self.get_active_delivery_zones()
                zone = next((candidate for candidate in zones if str(candidate.id) == str(zone_id)), None)
                if not zone:
                    raise DeliveryZone.DoesNotExist
                matching_ids = [
                    order['id']
                    for order in queryset.values(
                        'id',
                        'location_latitude',
                        'location_longitude',
                        'delivery_latitude',
                        'delivery_longitude',
                    )
                    if zone.contains_location(
                        order['delivery_latitude'] or order['location_latitude'],
                        order['delivery_longitude'] or order['location_longitude'],
                    )
                ]
                queryset = queryset.filter(id__in=matching_ids)
            except DeliveryZone.DoesNotExist:
                queryset = queryset.none()

        return queryset.annotate(
            priority=Case(
                When(status='pending', then=Value(0)),
                When(rider__isnull=True, then=Value(1)),
                When(status='confirmed', then=Value(2)),
                When(status='looking_for_rider', then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            )
        ).order_by('priority', '-created_at')

    def get_active_delivery_zones(self):
        if not hasattr(self, '_active_delivery_zones'):
            self._active_delivery_zones = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))
        return self._active_delivery_zones

    @swagger_auto_schema(
        operation_summary="List All Orders from Marketplace Vendors (Admin)",
        operation_description="Retrieve a paginated list of all orders from marketplace vendors only. Supports filtering by track ID, order status, and specific vendor.",
        manual_parameters=[
            openapi.Parameter(
                'track_id',
                openapi.IN_QUERY,
                description="Search orders by tracking ID (partial match allowed)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Filter orders by status (e.g., pending, shipped, delivered, canceled)",
                type=openapi.TYPE_STRING,
                enum=['pending', 'confirmed', 'preparing', 'looking_for_rider', 'rider_assigned', 'picked_up', 'in_transit', 'near_delivery', 'delivered', 'canceled', 'rejected', 'payment_failed'],
                required=False
            ),
            openapi.Parameter(
                'vendor_id',
                openapi.IN_QUERY,
                description="Filter orders by specific marketplace vendor ID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=False
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of orders to return per page",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of orders from marketplace vendors",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "data": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                description="Order object (serialized)",
                            )
                        )
                    }
                )
            ),
            401: "Unauthorized"
        }
    )
    def get(self, request):
        addition_serializer_data = {
            'is_vendor': True
        }
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            page_size=int(request.GET.get('page_size', 20)),
            addition_serializer_data=addition_serializer_data,
            extra_serializer_context={
                "active_delivery_zones": self.get_active_delivery_zones(),
            },
        )


class AdminOrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    queryset = Order.objects.select_related(
        'user',
        'vendor',
        'vendor__user',
        'rider',
        'rider__user',
    ).prefetch_related(
        'items',
        'items__product',
        'items__product__parent',
        'items__product__productimage_set',
        'items__product__parent__productimage_set',
        'items__product__productvariantcategory_set',
        'items__variant_selections',
        'items__variant_selections__variant',
        'items__variant_selections__variant__category',
        'items__variant_selections__variant__product',
    )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["active_delivery_zones"] = list(DeliveryZone.objects.filter(is_active=True).order_by('name'))
        return context

    @swagger_auto_schema(
        operation_description="Retrieve detailed information of a specific order by ID.",
        operation_summary="Admin Order Detail",
        responses={
            200: OrderSerializer(),
            401: "Unauthorized access.",
            404: "Order not found."
        },
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="UUID of the order",
                type=openapi.TYPE_STRING,
                required=True
            )
        ]
    )
    def get(self, request, *args, **kwargs):
        try:
            order = self.get_object()
            serializer = self.get_serializer(order, context={
                **self.get_serializer_context(),
                "include_delivery_info": True,
            })
            return success_response(serializer.data)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.")





class AdminOrderDetailVendorRiderAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    queryset = Order.objects.select_related('user', 'vendor', 'vendor__user', 'rider', 'rider__user')

    def get(self, request, *args, **kwargs):
        try:
            order:Order = self.get_object()
            response = {
                'user': None,
                'vendor': None,
                'rider': None

            }
            if order.user:
                response['user'] = dict(
                    id=order.user.id,
                    name=order.user.full_name or f"{order.user.first_name or ''} {order.user.last_name or ''}".strip() or order.user.email,
                    profile_image=order.user.get_profile_image(),
                    phone_number=order.user.phone_number,
                    email=order.user.email,
                )

            if order.vendor:
                response['vendor'] = dict(
                    id=order.vendor.id,
                    name=order.vendor.name or order.vendor.user.full_name or order.vendor.user.email,
                    profile_image=order.vendor.thumbnail_url or order.vendor.logo_url or order.vendor.user.get_profile_image(),
                    phone_number=getattr(order.vendor, 'phone_number', '') or order.vendor.user.phone_number,
                    email=getattr(order.vendor, 'email', '') or order.vendor.user.email,
                )
            if order.rider:
                response['rider'] = dict(
                    id=order.rider.id,
                    name=order.rider.user.full_name or f"{order.rider.user.first_name or ''} {order.rider.user.last_name or ''}".strip() or order.rider.user.email,
                    profile_image=order.rider.user.get_profile_image(),
                    phone_number=order.rider.user.phone_number,
                    email=order.rider.user.email,
                )
            return success_response(response)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.")
