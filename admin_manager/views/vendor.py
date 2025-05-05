from datetime import timedelta, timezone
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from account.models import Vendor
from django.db.models import Sum
from helpers.response.response_format import success_response, paginate_success_response_with_serializer, bad_request_response, internal_server_error_response
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi 

from product.models import Order, Product
from vendor.serializers import ProductSerializer, VendorSerializer





class AdminVendorListView(generics.ListAPIView):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    queryset = Vendor.objects.all()

    @swagger_auto_schema(
        operation_description="Get the details of a vendor.",
        operation_summary="Retrieve the details of a specific vendor.",
        responses={
            200: VendorSerializer,
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            page_size=int(request.GET.get('page_size',20))
        )






# class AdminVendorDetailView(generics.GenericAPIView):
#     serializer_class = VendorSerializer
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(
#         operation_description="Get the details of a vendor.",
#         operation_summary="Retrieve the details of a specific vendor.",
#         responses={
#             200: VendorSerializer,
#             404: "Vendor Not Found",
#             401: "Unauthorized",
#         }
#     )
#     def get(self, request, vendor_id):
#         vendor = Vendor.objects.get(id=vendor_id)
#         serializer = self.serializer_class(vendor)
#         return success_response(serializer.data)


# Update the existing AdminVendorDetailView to handle PUT for updates
class AdminVendorDetailView(generics.GenericAPIView):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get the details of a vendor.",
        operation_summary="Retrieve the details of a specific vendor.",
        responses={
            200: VendorSerializer,
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            serializer = self.serializer_class(vendor)
            return success_response(serializer.data)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")
    
    @swagger_auto_schema(
        operation_description="Update vendor details.",
        operation_summary="Update an existing vendor's information.",
        request_body=VendorSerializer,
        responses={
            200: VendorSerializer,
            400: "Bad Request",
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def put(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            serializer = self.serializer_class(vendor, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return success_response(serializer.data, message="Vendor updated successfully")
  
        except Vendor.DoesNotExist:
            return bad_request_response(message= "Vendor not found")
        

class AdminVendorOverviewView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get vendor overview and performance metrics.",
        operation_summary="Retrieve comprehensive vendor performance data.",
        manual_parameters=[
            openapi.Parameter(
                'time_frame', 
                openapi.IN_QUERY, 
                description="Time period for data (daily, weekly, monthly, yearly)", 
                type=openapi.TYPE_STRING,
                default='weekly'
            ),
        ],
        responses={
            200: "Vendor overview and performance data",
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            time_frame = request.GET.get('time_frame', 'weekly')
            
            # Get date range based on time_frame
            end_date = timezone.now()
            if time_frame == 'daily':
                start_date = end_date - timedelta(days=1)
            elif time_frame == 'weekly':
                start_date = end_date - timedelta(days=7)
            elif time_frame == 'monthly':
                start_date = end_date - timedelta(days=30)
            elif time_frame == 'yearly':
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date - timedelta(days=7)  # Default to weekly
            
            # Get orders for this vendor
            vendor_orders = Order.objects.filter(vendor=vendor)
            
            # Calculate order statistics
            total_orders = vendor_orders.count()
            active_orders = vendor_orders.filter(status='pending').count()
            completed_orders = vendor_orders.filter(status='delivered').count()
            canceled_orders = vendor_orders.filter(status='canceled').count()
            
            # Calculate financial metrics
            total_earnings = vendor_orders.filter(payment_status='paid').aggregate(
                total=Sum('total_amount')
            )['total'] or 0
            
            # Calculate payouts (assuming you have a Payout model or similar)
            # This is a placeholder; adjust according to your actual payment tracking system
            total_payouts = total_earnings * 0.9  # Example: 90% of earnings go to vendor
            pending_payouts = 0  # Placeholder - replace with actual calculation
            
            # Get recent reports or issues (placeholder)
            reports_count = 0  # Replace with actual report count if you have such a feature
            
            # Business details
            business_details = {
                "name": vendor.name,
                "type": vendor.category.name if vendor.category else "Not specified",
                "status": "Active" if vendor.is_active else "Inactive",
                "date_joined": vendor.created_at.strftime("%d/%m/%Y"),
                "rating": float(vendor.rating),
                "logo_url": request.build_absolute_uri(vendor.logo.url) if vendor.logo else None
            }
            
            # Order overview
            order_overview = {
                "total_orders": total_orders,
                "active_orders": active_orders,
                "completed_orders": completed_orders,
                "canceled_orders": canceled_orders,
                "time_frame": time_frame
            }
            
            # Sales performance
            sales_performance = {
                "total_earnings": float(total_earnings),
                "total_payouts": float(total_payouts),
                "pending_payouts": pending_payouts,
                "time_frame": time_frame
            }
            
            # Reports
            reports = {
                "count": reports_count,
                "details_url": f"/api/admin/vendor/{vendor_id}/reports"  # Placeholder URL
            }
            
            response_data = {
                "business_details": business_details,
                "order_overview": order_overview,
                "sales_performance": sales_performance,
                "reports": reports
            }
            
            return success_response(data=response_data)
            
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")
        except Exception as e:
            print(e)
            return internal_server_error_response()



class AdminVendorProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer  # Assuming you have a ProductSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        vendor_id = self.kwargs.get('vendor_id')
        return Product.objects.filter(vendor__id=vendor_id)
    
    @swagger_auto_schema(
        operation_description="Get all products belonging to a specific vendor.",
        operation_summary="Retrieve all products of a vendor.",
        responses={
            200: "List of vendor products",
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, vendor_id):
        try:
            # Check if vendor exists
            vendor = Vendor.objects.get(id=vendor_id)
            
            return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                self.get_queryset(),
                page_size=int(request.GET.get('page_size', 20))
            )
        except Vendor.DoesNotExist:
            return bad_request_response(message= "Vendor not found")


class AdminVendorSuspendView(generics.GenericAPIView):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Suspend or reactivate a vendor.",
        operation_summary="Toggle vendor's active status.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['is_active'],
            properties={
                'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Active status of the vendor')
            },
        ),
        responses={
            200: VendorSerializer,
            404: "Vendor Not Found",
            401: "Unauthorized",
            400: "Bad Request"
        }
    )
    def patch(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            
            # Get the is_active status from request data
            is_active = request.data.get('is_active')
            if is_active is None:
                return bad_request_response(message="is_active field is required")
            
            # Update vendor status
            vendor.is_active = is_active
            vendor.save()
            
            serializer = self.serializer_class(vendor)
            return success_response(serializer.data, message="Vendor status updated successfully")
            
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

class AdminVendorDeleteView(generics.DestroyAPIView):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    queryset = Vendor.objects.all()
    lookup_field = 'id'
    lookup_url_kwarg = 'vendor_id'
    
    @swagger_auto_schema(
        operation_description="Delete a vendor from the system.",
        operation_summary="Delete a vendor permanently.",
        responses={
            204: "Vendor deleted successfully",
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def delete(self, request, *args, **kwargs):
        try:
            vendor = self.get_object()
            vendor.delete()
            return success_response(message="Vendor deleted successfully",status_code=204)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")


