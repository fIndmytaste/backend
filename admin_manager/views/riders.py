from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from django.utils import timezone
from django.db.models import Avg, Count, Q, DecimalField
from account.models import Rider, RiderRating, User
from account.serializers import RiderDocumentverificationSerializer, RiderSerializer
from admin_manager.serializers.products import AdminProductCategoriesSerializer
from admin_manager.serializers.riders import RiderPerformanceMetricsSerializer
from helpers.response.response_format import paginate_success_response_with_serializer, success_response, bad_request_response, internal_server_error_response
from product.models import Order, Product, Rating, SystemCategory
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi
from datetime import timedelta, datetime
from decimal import Decimal

from product.serializers import OrderSerializer
from helpers.websocket_notification import notify_rider_order_assignment
from rider.serializers import RiderRatingCreateSerializer


class AdminRiderListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderSerializer
    queryset = Rider.objects.all()

    def get(self, request):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset().order_by('-created_at'),
            page_size=int(request.GET.get('page_size', 20))
        )


class AdminRiderRetrieveDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderSerializer
    queryset = Rider.objects.all()
    lookup_field = 'id'

    def get(self, request, *args, **kwargs):
        return success_response(
            self.serializer_class(self.get_object(),context={"request": request}).data
        )

    def patch(self, request, *args, **kwargs):
        super().patch(request, *args, **kwargs)
        return success_response(
            message="Rider deleted successfully",
        )


class AdminRiderDocumentverificationView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderDocumentverificationSerializer
    queryset = Rider.objects.all()
    lookup_field = 'id'

    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        rider = self.get_object()
        # Notify rider of verification status update
        from helpers.push_notification import notification_helper
        try:
            notification_helper(
                rider.user,
                "Document Verification Updated",
                f"Your document verification status has been updated to {rider.is_verified}.",
                {"type": "kyc_update", "is_verified": str(rider.is_verified)}
            )
        except Exception as e:
            print(f"Failed to send KYC notification: {e}")

        return success_response(
            message="Rider document status updated successfully",
        )


class AdminRiderOrderListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderSerializer
    queryset = Rider.objects.all()
    lookup_field = 'id'

    def get(self, request, id):
        try:
            rider = Rider.objects.get(id=id)
        except:
            return bad_request_response(
                message="Rider not found",
                status_code=404
            )
        orders = Order.objects.filter(rider=rider).order_by('-created_at')
        return paginate_success_response_with_serializer(
            request,
            OrderSerializer,
            orders,
            page_size=int(request.GET.get('page_size', 20))
        )


class AdminRiderReviewListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderRatingCreateSerializer
    queryset = Rider.objects.all()
    lookup_field = 'id'

    def get(self, request, id):
        try:
            rider = Rider.objects.get(id=id)
        except:
            return bad_request_response(
                message="Rider not found",
                status_code=404
            )

        reviews = RiderRating.objects.filter(
            rider=rider).order_by('-created_at')
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            reviews,
            page_size=10
        )


class RiderEarningMetricsView(generics.GenericAPIView):

    permission_classes = [IsAuthenticated]
    serializer_class = RiderPerformanceMetricsSerializer
    lookup_field = 'id'

    def get(self, request, id):
        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(
                message='Rider not found',
                status_code=404
            )

        from wallet.models import Wallet
        wallet, _ = Wallet.objects.get_or_create(user=rider.user)

        total_earnings = wallet.transactions.filter(transaction_type='earning', status='completed').aggregate(
            sum_amount=Sum('amount'))['sum_amount'] or 0
        total_payout = wallet.transactions.filter(transaction_type='withdrawal', status='completed').aggregate(
            sum_amount=Sum('amount'))['sum_amount'] or 0

        response = {
            'total_earnings': float(total_earnings),
            'total_payout': float(total_payout),
            'balance': float(wallet.balance),
        }
        return success_response(data=response)


class RiderPerformanceMetricsView(generics.GenericAPIView):
    """
    Get performance metrics for a specific rider
    Query parameters:
    - period: 'weekly', 'monthly', 'yearly' (default: 'weekly')
    - start_date: YYYY-MM-DD (optional, overrides period)  
    - end_date: YYYY-MM-DD (optional, overrides period)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = RiderPerformanceMetricsSerializer
    lookup_field = 'id'

    def get(self, request, id):
        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(
                message='Rider not found',
                status_code=404
            )

        # Get date range
        period = request.GET.get('period', 'weekly').lower()
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                period_text = f"{start_date} to {end_date}"
            except ValueError:
                return bad_request_response(
                    message='Invalid date format. Use YYYY-MM-DD'
                )
        else:
            # Calculate date range based on period
            now = timezone.now().date()
            if period == 'weekly':
                start_date = now - timedelta(days=7)
                period_text = "Last 7 days"
            elif period == 'monthly':
                start_date = now - timedelta(days=30)
                period_text = "Last 30 days"
            elif period == 'yearly':
                start_date = now - timedelta(days=365)
                period_text = "Last 365 days"
            else:
                start_date = now - timedelta(days=7)
                period_text = "Last 7 days"

            end_date = now

        # Get orders in the specified period
        orders_queryset = Order.objects.filter(
            rider=rider,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        # Calculate metrics
        metrics = self._calculate_metrics(orders_queryset, rider, period_text)

        serializer = self.serializer_class(data=metrics)
        if serializer.is_valid():
            return success_response(
                data=serializer.data,
                message='Performance metrics retrieved successfully'
            )

        return internal_server_error_response(
            message='Error calculating metrics'
        )

    def _calculate_metrics(self, orders_queryset, rider, period_text):
        """Calculate performance metrics for the rider"""

        # Total orders
        total_orders = orders_queryset.count()

        # Completed orders (delivered)
        completed_orders = orders_queryset.filter(status='delivered').count()

        # Canceled orders
        canceled_orders = orders_queryset.filter(status='canceled').count()

        # Completion rate
        completion_rate = Decimal('0.00')
        if total_orders > 0:
            completion_rate = Decimal(
                completed_orders) / Decimal(total_orders) * Decimal('100.00')

        # Average delivery time (for completed orders only)
        delivered_orders = orders_queryset.filter(
            status='delivered',
            actual_pickup_time__isnull=False,
            actual_delivery_time__isnull=False
        )

        average_delivery_time = "N/A"
        if delivered_orders.exists():
            # Calculate average delivery time in minutes
            delivery_times = []
            for order in delivered_orders:
                if order.actual_pickup_time and order.actual_delivery_time:
                    time_diff = order.actual_delivery_time - order.actual_pickup_time
                    # Convert to minutes
                    delivery_times.append(time_diff.total_seconds() / 60)

            if delivery_times:
                avg_minutes = sum(delivery_times) / len(delivery_times)
                average_delivery_time = f"{int(avg_minutes)}mins"

        # On-time deliveries (delivered within estimated time)
        on_time_deliveries = 0
        for order in delivered_orders:
            if (order.estimated_delivery_time and
                order.actual_delivery_time and
                    order.actual_delivery_time <= order.estimated_delivery_time):
                on_time_deliveries += 1

        # Overall rating
        ratings = RiderRating.objects.filter(rider=rider)
        overall_rating = ratings.aggregate(
            avg_rating=Avg('rating'))['avg_rating']
        if overall_rating is None:
            overall_rating = Decimal('0.00')
        else:
            overall_rating = round(overall_rating, 2)

        return {
            'average_delivery_time': average_delivery_time,
            'on_time_deliveries': on_time_deliveries,
            'canceled_orders': canceled_orders,
            'overall_rating': overall_rating,
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'completion_rate': completion_rate,
            'period': period_text
        }


class AllRidersPerformanceMetricsView(generics.GenericAPIView):
    """
    Get performance metrics for all riders (Admin view)
    Query parameters:
    - period: 'weekly', 'monthly', 'yearly' (default: 'weekly')
    - start_date: YYYY-MM-DD (optional)
    - end_date: YYYY-MM-DD (optional)
    - page_size: number of riders per page (default: 20)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get date range (same logic as single rider view)
        period = request.GET.get('period', 'weekly').lower()
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        page_size = int(request.GET.get('page_size', 20))

        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                period_text = f"{start_date} to {end_date}"
            except ValueError:
                return bad_request_response(
                    message='Invalid date format. Use YYYY-MM-DD'
                )
        else:
            now = timezone.now().date()
            if period == 'weekly':
                start_date = now - timedelta(days=7)
                period_text = "Last 7 days"
            elif period == 'monthly':
                start_date = now - timedelta(days=30)
                period_text = "Last 30 days"
            elif period == 'yearly':
                start_date = now - timedelta(days=365)
                period_text = "Last 365 days"
            else:
                start_date = now - timedelta(days=7)
                period_text = "Last 7 days"

            end_date = now

        # Get all riders with orders in the period
        riders = Rider.objects.filter(
            orders__created_at__date__gte=start_date,
            orders__created_at__date__lte=end_date
        ).distinct()

        # Calculate metrics for each rider
        riders_metrics = []
        for rider in riders:
            orders_queryset = Order.objects.filter(
                rider=rider,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )

            metrics = self._calculate_metrics(
                orders_queryset, rider, period_text)
            metrics['rider_id'] = str(rider.id)
            metrics['rider_name'] = rider.user.get_full_name(
            ) or rider.user.username
            metrics['rider_email'] = rider.user.email

            riders_metrics.append(metrics)

        # Sort by completion rate (highest first)
        riders_metrics.sort(key=lambda x: x['completion_rate'], reverse=True)

        # Simple pagination
        page = int(request.GET.get('page', 1))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_metrics = riders_metrics[start_idx:end_idx]

        return success_response(
            data={
                'riders': paginated_metrics,
                'period': period_text,
                'total_riders': len(riders_metrics),
                'page': page,
                'page_size': page_size,
                'has_next': end_idx < len(riders_metrics)
            },
            message='All riders performance metrics retrieved successfully'
        )

    def _calculate_metrics(self, orders_queryset, rider, period_text):
        """Same calculation logic as single rider view"""
        total_orders = orders_queryset.count()
        completed_orders = orders_queryset.filter(status='delivered').count()
        canceled_orders = orders_queryset.filter(status='canceled').count()

        completion_rate = Decimal('0.00')
        if total_orders > 0:
            completion_rate = Decimal(
                completed_orders) / Decimal(total_orders) * Decimal('100.00')

        delivered_orders = orders_queryset.filter(
            status='delivered',
            actual_pickup_time__isnull=False,
            actual_delivery_time__isnull=False
        )

        average_delivery_time = "N/A"
        if delivered_orders.exists():
            delivery_times = []
            for order in delivered_orders:
                if order.actual_pickup_time and order.actual_delivery_time:
                    time_diff = order.actual_delivery_time - order.actual_pickup_time
                    delivery_times.append(time_diff.total_seconds() / 60)

            if delivery_times:
                avg_minutes = sum(delivery_times) / len(delivery_times)
                average_delivery_time = f"{int(avg_minutes)}mins"

        on_time_deliveries = 0
        for order in delivered_orders:
            if (order.estimated_delivery_time and
                order.actual_delivery_time and
                    order.actual_delivery_time <= order.estimated_delivery_time):
                on_time_deliveries += 1

        ratings = RiderRating.objects.filter(rider=rider)
        overall_rating = ratings.aggregate(
            avg_rating=Avg('rating'))['avg_rating']
        if overall_rating is None:
            overall_rating = Decimal('0.00')
        else:
            overall_rating = round(overall_rating, 2)

        return {
            'average_delivery_time': average_delivery_time,
            'on_time_deliveries': on_time_deliveries,
            'canceled_orders': canceled_orders,
            'overall_rating': overall_rating,
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'completion_rate': completion_rate,
            'period': period_text
        }


class AdminAssignOrderToRiderView(generics.GenericAPIView):
    """
    Assign an order to a rider (Admin action)
    POST body: { "order_id": "<uuid>" }
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def post(self, request, id):
        order_id = request.data.get('order_id')
        if not order_id:
            return bad_request_response(message="order_id is required.")
        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(message="Rider not found.", status_code=404)
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.", status_code=404)
        # Business rule: Only assign if order is unassigned
        if order.rider:
            return bad_request_response(message="Order already assigned to a rider.")

        order.rider = rider
        order.status = 'rider_assigned'
        order.delivery_status = 'rider_assigned'
        order.save()
        notify_rider_order_assignment(order, rider)
        return success_response(message="Order assigned to rider successfully.", data={"order_id": str(order.id), "rider_id": str(rider.id)})


class AdminRiderAccountControlView(generics.GenericAPIView):
    """
    Suspend or ban a rider.
    POST body: { "action": "suspend" | "ban" | "activate", "reason": "string" }
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def post(self, request, id):
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(message="Rider not found.", status_code=404)

        if action == 'suspend':
            rider.status = 'suspended'
            rider.is_verified = False  # Temporary block
        elif action == 'ban':
            rider.status = 'banned'
            rider.user.is_active = False
            rider.user.save()
        elif action == 'activate':
            rider.status = 'active'
            rider.is_verified = True
            rider.user.is_active = True
            rider.user.save()
        else:
            return bad_request_response(message="Invalid action. Use 'suspend', 'ban', or 'activate'.")

        rider.save()
        return success_response(message=f"Rider account {action}ed successfully.", data={"rider_id": str(rider.id), "status": rider.status})


class AdminMarketplaceAssignOrderView(generics.GenericAPIView):
    """
    Manually assign a marketplace order to a fixed-salary (in-house) rider.
    POST body: { "order_id": "<uuid>", "rider_id": "<uuid>" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')
        rider_id = request.data.get('rider_id')

        try:
            order = Order.objects.get(id=order_id)
            rider = Rider.objects.get(id=rider_id)
        except (Order.DoesNotExist, Rider.DoesNotExist):
            return bad_request_response(message="Order or Rider not found.", status_code=404)

        if not rider.is_in_house_rider:
            return bad_request_response(message="Rider is not an in-house/marketplace rider.")

        order.rider = rider
        order.status = 'rider_assigned'
        order.save()
        notify_rider_order_assignment(order, rider)

        return success_response(message="Marketplace order assigned manually.", data={"order_id": str(order.id), "rider_id": str(rider.id)})


class RiderAdvancePaymentView(generics.GenericAPIView):
    """
    Release pending funds as an advance payment.
    POST body: { "amount": float, "reason": "string" }
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def post(self, request, id):
        from decimal import Decimal
        amount = Decimal(str(request.data.get('amount', 0)))
        reason = request.data.get('reason', 'Advance Payment')

        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(message="Rider not found.", status_code=404)

        from wallet.models import Wallet, WalletTransaction
        wallet, _ = Wallet.objects.get_or_create(user=rider.user)

        # Process advance payment
        wallet.deposit(amount)

        WalletTransaction.objects.create(
            wallet=wallet,
            user=rider.user,
            amount=amount,
            transaction_type='deposit',
            status='completed',
            description=f"Advance Payment: {reason}"
        )

        return success_response(message="Advance payment processed successfully.", data={"rider_id": str(rider.id), "amount": float(amount)})
