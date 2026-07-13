from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, timedelta
from account.models import User
from helpers.response.response_format import success_response, paginate_success_response_with_serializer, bad_request_response, internal_server_error_response
from helpers.date_range import filter_by_date_range
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi 

from account.serializers import UserSerializer
from admin_manager.serializers.lists import AdminUserListSerializer
from product.models import Order
from product.serializers import OrderSerializer

# Let's assume you have a User model with fields like is_active, last_login, etc.
# You'll need to adapt this to your actual User model

class AdminCustomerListView(generics.ListAPIView):
    serializer_class = AdminUserListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter users with 'buyer' role
        return User.objects.filter(role='buyer').only(
            'id',
            'email',
            'full_name',
            'first_name',
            'last_name',
            'is_active',
            'role',
            'phone_number',
            'profile_image_url',
            'is_verified',
            'created_at',
            'updated_at',
        ).order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get a list of all customers (users with buyer role).",
        operation_summary="List all customers",
        manual_parameters=[
            openapi.Parameter(
                'search', 
                openapi.IN_QUERY, 
                description="Search by name, email or phone number", 
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'status', 
                openapi.IN_QUERY, 
                description="Filter by account status (active, suspended, banned)", 
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'page_size', 
                openapi.IN_QUERY, 
                description="Number of results per page", 
                type=openapi.TYPE_INTEGER,
                default=10
            ),
        ],
        responses={
            200: "List of customers",
            401: "Unauthorized",
        }
    )
    def get(self, request):
        queryset = self.get_queryset()
        
        # Handle search functionality
        search = request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) | 
                Q(phone_number__icontains=search)
            )
            
        # Handle status filtering
        status = request.GET.get('status', '')
        if status:
            if status.lower() == 'active':
                queryset = queryset.filter(is_active=True)
            elif status.lower() in ('suspended', 'banned'):
                queryset = queryset.filter(is_active=False)

        # Handle custom date range filtering (registration date)
        queryset = filter_by_date_range(request, queryset)

        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            queryset,
            page_size=int(request.GET.get('page_size', 10))
        )


class AdminCustomerDetailView(generics.GenericAPIView):
    serializer_class = UserSerializer  # Assuming you have a UserSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get detailed information about a specific customer.",
        operation_summary="Retrieve customer details",
        responses={
            200: UserSerializer,
            404: "Customer Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='buyer')

            # Get user details
            serializer = self.serializer_class(user)
            user_data = serializer.data

            # Calculate time since last login
            if user.last_login:
                now = timezone.now()
                time_diff = now - user.last_login

                # Format the time difference in a human-readable way
                if time_diff.days > 0:
                    last_login = f"{time_diff.days} days ago"
                elif time_diff.seconds // 3600 > 0:
                    last_login = f"{time_diff.seconds // 3600} hours ago"
                elif time_diff.seconds // 60 > 0:
                    last_login = f"{time_diff.seconds // 60} minutes ago"
                else:
                    last_login = f"{time_diff.seconds} seconds ago"
            else:
                last_login = "Never"

            # Add last login information
            user_data['last_login_formatted'] = last_login

            # Customer orders: only the plain columns the admin table renders.
            # The full OrderSerializer (nested items, delivery-zone lookups,
            # commission calcs) made this endpoint time out for customers
            # with large order histories.
            orders = list(
                Order.objects.filter(user=user)
                .order_by('-created_at')
                .values(
                    'id',
                    'track_id',
                    'total_amount',
                    'status',
                    'delivery_status',
                    'payment_status',
                    'created_at',
                )
            )
            for order in orders:
                order['id'] = str(order['id'])
                order['total_amount'] = float(order['total_amount'] or 0)
                order['created_at'] = order['created_at'].isoformat() if order['created_at'] else None

            response_data = {
                "customer_details": user_data,
                "orders": orders,
            }

            return success_response(data=response_data)

        except User.DoesNotExist:
            return bad_request_response(message="Customer not found")


class AdminCustomerSuspendView(generics.GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Suspend or reactivate a customer account.",
        operation_summary="Toggle customer's active status.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['is_active'],
            properties={
                'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Active status of the customer')
            },
        ),
        responses={
            200: "Customer status updated successfully",
            404: "Customer Not Found",
            401: "Unauthorized",
            400: "Bad Request"
        }
    )
    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='buyer')
            
            # Get the is_active status from request data
            is_active = request.data.get('is_active')
            if is_active is None:
                return bad_request_response(message="is_active field is required")
            
            # Update user status
            user.is_active = is_active
            user.save()
            
            status_text = "activated" if is_active else "suspended"
            
            return success_response(message=f"Customer has been {status_text} successfully")
            
        except User.DoesNotExist:
            return bad_request_response(message="Customer not found")


class AdminCustomerDeleteView(generics.DestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return User.objects.filter(role='buyer')
    
    @swagger_auto_schema(
        operation_description="Delete a customer account.",
        operation_summary="Delete a customer permanently.",
        responses={
            204: "Customer deleted successfully",
            404: "Customer Not Found",
            401: "Unauthorized",
        }
    )
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='buyer')
            user.delete()
            return success_response(message= "Customer deleted successfully",status_code=204)
        except User.DoesNotExist:
            return bad_request_response(message="Customer not found")


class AdminCustomerBanView(generics.GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Ban or unban a customer account.",
        operation_summary="Toggle customer's banned status.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['is_banned'],
            properties={
                'is_banned': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Banned status of the customer'),
                'reason': openapi.Schema(type=openapi.TYPE_STRING, description='Reason for banning the customer')
            },
        ),
        responses={
            200: "Customer ban status updated successfully",
            404: "Customer Not Found",
            401: "Unauthorized",
            400: "Bad Request"
        }
    )
    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='buyer')
            
            # Get the is_banned status from request data
            is_banned = request.data.get('is_banned')
            reason = request.data.get('reason', '')
            
            if is_banned is None:
                return Response(
                    {"detail": "is_banned field is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update user status
            user.is_banned = is_banned
            # If your model has a ban_reason field, you could set it here
            # user.ban_reason = reason if is_banned else ""
            user.save()
            
            status_text = "banned" if is_banned else "unbanned"
            
            return Response(
                {"detail": f"Customer has been {status_text} successfully"}, 
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response({"detail": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)


class AdminCustomerOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer  # Assuming you have an OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        queryset = Order.objects.filter(user_id=user_id).order_by('-created_at')
        return filter_by_date_range(self.request, queryset)
    
    @swagger_auto_schema(
        operation_description="Get all orders made by a specific customer.",
        operation_summary="List customer's orders",
        responses={
            200: "List of customer orders",
            404: "Customer Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, user_id):
        try:
            # Verify the user exists
            user = User.objects.get(id=user_id, role='buyer')
            
            return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                self.get_queryset(),
                page_size=int(request.GET.get('page_size', 10))
            )
            
        except User.DoesNotExist:
            return Response({"detail": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        



class AdminCustomerOrdersOverviewView(generics.ListAPIView):
    serializer_class = OrderSerializer  # Assuming you have an OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        return Order.objects.filter(user_id=user_id).order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get all orders made by a specific customer.",
        operation_summary="List customer's orders",
        responses={
            200: "List of customer orders",
            404: "Customer Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, user_id):
        from django.utils import timezone
        try:
            # Verify the user exists
            user = User.objects.get(id=user_id, role='buyer')
        except User.DoesNotExist:
            return Response({"detail": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        
        
        try:
            time_frame = request.GET.get('time_frame', 'weekly')
            
            end_date = timezone.now()
  
            # Get orders for this vendor
            customer_orders = filter_by_date_range(
                request,
                Order.objects.filter(user=user),
            )
            
            # Calculate order statistics (same status buckets as the vendor
            # overview so "active" covers every in-progress state).
            total_orders = customer_orders.count()
            active_orders = customer_orders.filter(
                status__in=[
                    'pending',
                    'confirmed',
                    'preparing',
                    'looking_for_rider',
                    'rider_assigned',
                    'picked_up',
                    'in_transit',
                    'near_delivery',
                ]
            ).count()
            completed_orders = customer_orders.filter(status='delivered').count()
            canceled_orders = customer_orders.filter(
                status__in=['canceled', 'cancelled', 'rejected']
            ).count()
            
          
            # Order overview
            order_overview = {
                "total_orders": total_orders,
                "active_orders": active_orders,
                "completed_orders": completed_orders,
                "canceled_orders": canceled_orders,
                "time_frame": time_frame
            }
            

            
            return success_response(data=order_overview)

        except Exception as e:
            print(e)
            return internal_server_error_response()
