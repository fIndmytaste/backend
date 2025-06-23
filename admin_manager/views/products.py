from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

from account.models import Rider, User
from account.serializers import RiderSerializer
from admin_manager.serializers.products import AdminProductCategoriesSerializer
from helpers.response.response_format import paginate_success_response_with_serializer, success_response,bad_request_response
from product.models import Order, Product, Rating, SystemCategory
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi 

from product.serializers import OrderSerializer, RatingSerializer
from vendor.serializers import ProductSerializer


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
    permission_classes = [IsAuthenticated]

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
        responses={
            200: openapi.Response(
                description="Dashboard metrics successfully retrieved.",
                examples={
                    "application/json": {
                        "success": True,
                        "data": {
                            "order_overview": {
                                "total_orders": {"value": 120, "growth": True},
                                "active_orders": {"value": 25},
                                "completed_orders": {"value": 80},
                                "canceled_orders": {"value": 15}
                            },
                            "revenue_summary": {
                                "total_earnings": {"value": 25400.00, "growth": True},
                                "vendor_payouts": {"value": 22860.00}
                            },
                            "user_metrics": {
                                "active_users": {"value": 140, "growth": True},
                                "new_users": {"value": 30},
                                "vendors": {"value": 12},
                                "riders": {"value": 5}
                            }
                        }
                    }
                }
            ),
            401: "Unauthorized"
        }
    )
    def get(self, request):
        # Get time range filter (default to weekly)
        time_range = request.query_params.get('time_range', 'week')
        
        # Calculate date range based on filter
        today = timezone.now()
        if time_range == 'week':
            start_date = today - timedelta(days=7)
        elif time_range == 'month':
            start_date = today - timedelta(days=30)
        elif time_range == 'year':
            start_date = today - timedelta(days=365)
        else:
            start_date = today - timedelta(days=7)  # Default to weekly
        
        # Get orders data
        total_orders = Order.objects.filter(created_at__gte=start_date).count()
        active_orders = Order.objects.filter(status='pending', created_at__gte=start_date).count()
        completed_orders = Order.objects.filter(status='delivered', created_at__gte=start_date).count()
        canceled_orders = Order.objects.filter(status='canceled', created_at__gte=start_date).count()
        
        # Get revenue data
        total_earnings = Order.objects.filter(
            payment_status='paid', 
            created_at__gte=start_date
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Calculate vendor payouts
        # Assuming vendor gets 90% of order amount, adjust as needed
        print(total_earnings)
        vendor_payouts = float(total_earnings) * 0.9
        
        # Get user metrics
        active_users = User.objects.filter(
            is_active=True, 
            last_login__gte=start_date
        ).count()
        
        new_users = User.objects.filter(
            created_at__gte=start_date
        ).count()
        
        vendors_count = User.objects.filter(
            role='vendor',
            created_at__gte=start_date
        ).count()
        
        riders_count = User.objects.filter(
            role='rider',
            created_at__gte=start_date
        ).count()
        
        # Check if there's growth compared to previous period
        previous_start = start_date - (today - start_date)
        previous_end = start_date
        
        prev_total_orders = Order.objects.filter(
            created_at__gte=previous_start,
            created_at__lt=previous_end
        ).count()
        
        prev_active_users = User.objects.filter(
            is_active=True,
            last_login__gte=previous_start,
            last_login__lt=previous_end
        ).count()
        
        prev_total_earnings = Order.objects.filter(
            payment_status='paid',
            created_at__gte=previous_start,
            created_at__lt=previous_end
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Calculate growth indicators
        order_growth = (total_orders > prev_total_orders) if prev_total_orders > 0 else True
        user_growth = (active_users > prev_active_users) if prev_active_users > 0 else True
        earnings_growth = (total_earnings > prev_total_earnings) if prev_total_earnings > 0 else True
        
        return success_response(data={
            "order_overview": {
                "total_orders": {
                    "value": total_orders,
                    "growth": order_growth
                },
                "active_orders": {
                    "value": active_orders
                },
                "completed_orders": {
                    "value": completed_orders
                },
                "canceled_orders": {
                    "value": canceled_orders
                }
            },
            "revenue_summary": {
                "total_earnings": {
                    "value": float(total_earnings),
                    "growth": earnings_growth
                },
                "vendor_payouts": {
                    "value": float(vendor_payouts)
                }
            },
            "user_metrics": {
                "active_users": {
                    "value": active_users,
                    "growth": user_growth
                },
                "new_users": {
                    "value": new_users
                },
                "vendors": {
                    "value": vendors_count
                },
                "riders": {
                    "value": riders_count
                }
            }
        })




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
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all().order_by('-created_at')


    def get_queryset(self):
        queryset = super().get_queryset()
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
    def get(self,request):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            page_size=int(request.GET.get('page_size',20))
        )



class AdminOrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    queryset = Order.objects.all()

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
            serializer = self.get_serializer(order)
            return success_response(serializer.data)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.")





class AdminOrderDetailVendorRiderAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    queryset = Order.objects.all()

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
                    profile_image=order.user.get_profile_image(),
                    phone_number=order.user.phone_number
                )

            if order.vendor:
                response['vendor'] = dict(
                    id=order.vendor.id,
                    profile_image=order.vendor.user.get_profile_image(),
                    phone_number=order.vendor.user.phone_number
                )
            if order.rider:
                response['rider'] = dict(
                    id=order.rider.id,
                    profile_image=order.rider.user.get_profile_image(),
                    phone_number=order.rider.user.phone_number
                )
            return success_response(response)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.")
