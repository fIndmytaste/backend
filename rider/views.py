# views.py
import json
import math
import random
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from helpers.websocket_notification import (
    get_order_dispatch_radius_km,
    is_order_visible_to_rider,
    notify_rider_order_assignment,
    notify_order_unavailable_to_riders,
    send_order_accepted_notification_customer,
)
from django.db import transaction
from django.db.models import Sum
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
from account.models import Guarantor, Notification, Rider, RiderRating, User, MODE_OF_TRANSPORTATION
from helpers.paystack import PaystackManager
from helpers.response.response_format import success_response, bad_request_response, internal_server_error_response, paginate_success_response_with_serializer
from product.models import DeliveryTracking, Order, DeclinedOrder
from wallet.models import Wallet, WalletTransaction
from wallet.serializers import get_minimum_withdrawal_for_user
from .serializers import (
    AcceptOrderSerializer,
    OrderSerializer,
    RiderDocumentUploadSerializer,
    RiderRatingCreateSerializer,
    RiderSerializer,
    DeliveryTrackingSerializer,
    RiderLocationUpdateSerializer
)
from helpers.push_notification import notification_helper, send_order_payment_success_notification
from helpers.order_utils import get_distance_between_two_location
from helpers.referral_logic import process_referral_reward
from decimal import Decimal


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        base_qs = (
            Order.objects
            .select_related('vendor__user', 'rider__user', 'user')
            .prefetch_related(
                'items__product__productimage_set',
                'items__variant_selections__variant__category',
            )
        )
        if hasattr(user, 'rider'):
            return base_qs.filter(rider=user.rider)
        elif hasattr(user, 'vendor'):
            return base_qs.filter(vendor=user.vendor)
        else:
            return base_qs.filter(user=user)

    @action(detail=True, methods=['post'])
    def assign_rider(self, request, pk=None):
        order = self.get_object()
        rider_id = request.data.get('rider_id')

        if not rider_id:
            return Response({'error': 'Rider ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rider = Rider.objects.get(id=rider_id)
            order.assign_rider(rider)
            notify_rider_order_assignment(order, rider)
            return Response({'status': 'Rider assigned successfully'})
        except Rider.DoesNotExist:
            return Response({'error': 'Rider not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def tracking(self, request, pk=None):
        order = self.get_object()
        tracking_data = order.get_delivery_status()
        return Response(tracking_data)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        status = request.data.get('status')

        if not status:
            return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Map status strings to corresponding order methods
        status_methods = {
            'picked_up': order.mark_as_picked_up,
            'in_transit': order.mark_as_in_transit,
            'near_delivery': order.mark_as_near_delivery,
            'delivered': order.mark_as_delivered
        }

        if status in status_methods:
            status_methods[status]()
            return Response({'status': f'Order marked as {status}'})
        else:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)


class MakeOrderPayment(generics.GenericAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        payment_method = request.data.get('payment_method')
        try:
            order = Order.objects.get(id=id)
        except:
            return bad_request_response(
                message='Order not found',
                status_code=404
            )

        user: User = request.user
        wallet, _ = Wallet.objects.get_or_create(user=user)

        order_total_price = order.get_total_price() + order.delivery_fee + \
            order.service_fee

        if not payment_method:
            if order.payment_method == 'wallet':
                if float(order_total_price) > float(wallet.balance):
                    return bad_request_response(
                        message='Insufficient balance. Please top up your wallet',
                    )
                # proceed the payment
                wallet.balance -= order_total_price
                wallet.save()
                order.status = 'paid'
                order.save()

                # Process referral reward if applicable
                process_referral_reward(order)

                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=order_total_price,
                    transaction_type='purchase',
                    description='Payment for order',
                    status='completed',
                    order=order
                )

                return success_response(
                    message='Payment successful'
                )
        # else:
        if not request.data.get('callback_url'):
            return bad_request_response(
                message="callback url (callback_url) is required for other payment method"
            )
        klass = PaystackManager()
        order.payment_method = payment_method
        order.save()
        return klass.initiate_payment(request, order_total_price, order)


class MakeOrderPayment(generics.GenericAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        payment_method = request.data.get('payment_method')
        try:
            order = Order.objects.get(id=id)
        except:
            return bad_request_response(
                message='Order not found',
                status_code=404
            )

        user: User = request.user
        wallet, _ = Wallet.objects.get_or_create(user=user)

        order_total_price = order.get_total_price() + order.delivery_fee + \
            order.service_fee

        if not payment_method:
            if order.payment_method == 'wallet':
                if float(order_total_price) > float(wallet.balance):
                    return bad_request_response(
                        message='Insufficient balance. Please top up your wallet',
                    )
                # proceed the payment
                wallet.balance -= order_total_price
                wallet.save()
                order.status = 'paid'
                order.save()

                # Process referral reward if applicable
                process_referral_reward(order)

                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=order_total_price,
                    transaction_type='purchase',
                    description='Payment for order',
                    status='completed',
                    order=order
                )

                return success_response(
                    message='Payment successful'
                )
        # else:
        if not request.data.get('callback_url'):
            return bad_request_response(
                message="callback url (callback_url) is required for other payment method"
            )
        klass = PaystackManager()
        order.payment_method = payment_method
        order.save()
        return klass.initiate_payment(request, order_total_price, order)


class ConfirmOrderPaymentAPIView(generics.GenericAPIView):
    permission_classes = []

    def _mark_order_payment_failed(self, transaction, response_payload=None, reference=None):
        if not transaction:
            return None

        order = transaction.order
        if order:
            should_notify = order.status != 'failed' or order.payment_status != Order.FAILED
            order.payment_status = Order.FAILED
            order.status = 'failed'
            order.save(update_fields=['payment_status', 'status', 'updated_at'])

            if should_notify:
                Notification.objects.create(
                    user=order.user,
                    title="Payment Verification Failed",
                    content=f"Payment for order #{order.track_id} could not be verified. The order has been moved to your history as failed.",
                )

                try:
                    notification_helper.send_to_user_async(
                        user=order.user,
                        title="Payment Verification Failed",
                        body=f"Payment for order #{order.track_id} could not be verified.",
                        data={
                            "type": "order_status_update",
                            "order_id": str(order.id),
                            "status": "failed",
                            "order_status": order.status,
                            "track_id": str(order.track_id),
                        },
                    )
                except Exception as exc:
                    print(f"Customer payment failure notification error: {exc}")

        transaction.status = 'failed'
        transaction.response_data = response_payload
        if reference:
            transaction.external_reference = reference
        transaction.description = 'Order Payment Failed'
        transaction.save()
        return order

    def _find_transaction(self, reference):
        if not reference:
            return None

        return WalletTransaction.objects.filter(
            external_reference=reference
        ).select_related('order').first()

    def _find_transaction_from_metadata(self, metadata):
        transaction_ref = metadata.get('reference')
        if transaction_ref:
            transaction = WalletTransaction.objects.filter(
                id=transaction_ref
            ).select_related('order').first()
            if transaction:
                return transaction

        order_ref = (
            metadata.get('order_id')
            or metadata.get('order_reference')
            or metadata.get('reference_code')
        )
        if order_ref:
            transaction = WalletTransaction.objects.filter(
                order_id=order_ref
            ).select_related('order').first()
            if transaction:
                return transaction

        custom_fields = metadata.get('custom_fields') or []
        for field in custom_fields:
            variable_name = field.get('variable_name')
            value = field.get('value')
            if variable_name in {'order_id', 'order_reference'} and value:
                transaction = WalletTransaction.objects.filter(
                    order_id=value
                ).select_related('order').first()
                if transaction:
                    return transaction

        return None

    def post(self, request):
        data = request.data
        try:
            reference = data.get('reference')
            transaction_reference = data.get('transaction_reference')
            trx_extist = self._find_transaction(reference)
            if not trx_extist and transaction_reference:
                trx_extist = WalletTransaction.objects.filter(
                    id=transaction_reference
                ).select_related('order').first()
            if not trx_extist and reference:
                trx_extist = WalletTransaction.objects.filter(
                    order_id=reference
                ).select_related('order').first()

            # verify transaction with paytsack
            klass = PaystackManager()
            success, response = klass.verify_transaction(reference)
            if not success:
                failed_order = self._mark_order_payment_failed(
                    trx_extist,
                    response_payload=response,
                    reference=reference,
                )
                return bad_request_response(
                    message="Payment verification failed",
                    data=OrderSerializer(failed_order).data if failed_order else None,
                )

            metadata = response.get('data', {}).get('metadata', {})
            # print(json.dumps(response.get('data',{})))
            print(response.get('data', {}).get('metadata', {}))
            trx_extist = trx_extist or self._find_transaction_from_metadata(metadata)
            if not metadata:
                failed_order = self._mark_order_payment_failed(
                    trx_extist,
                    response_payload=response,
                    reference=reference,
                )
                return bad_request_response(
                    message="Transaction does not exist",
                    data=OrderSerializer(failed_order).data if failed_order else None,
                )

            transaction_ref = metadata.get('reference')
            if transaction_ref:
                try:
                    trx_extist = WalletTransaction.objects.get(id=transaction_ref)
                except:
                    trx_extist = trx_extist or self._find_transaction_from_metadata(metadata)

            if not trx_extist:
                failed_order = self._mark_order_payment_failed(
                    trx_extist,
                    response_payload=response,
                    reference=reference,
                )
                return bad_request_response(
                    message="Transaction does not exist",
                    data=OrderSerializer(failed_order).data if failed_order else None,
                )

            if trx_extist.external_reference:
                if trx_extist.external_reference != reference:
                    failed_order = self._mark_order_payment_failed(
                        trx_extist,
                        response_payload=response,
                        reference=reference,
                    )
                    return bad_request_response(
                        message="Transaction does not exist",
                        data=OrderSerializer(failed_order).data if failed_order else None,
                    )


            if response['data'].get('status') == 'success':
                #  confirm the amount paid
                order = trx_extist.order
                amount_paid = (response['data']['amount']) / 100
                if float(amount_paid) != float(trx_extist.amount):
                    failed_order = self._mark_order_payment_failed(
                        trx_extist,
                        response_payload=response,
                        reference=reference,
                    )
                    return bad_request_response(
                        message="Transaction does not exist. Amount paid does not match",
                        data=OrderSerializer(failed_order).data if failed_order else None,
                    )

                if trx_extist.status != 'completed':
                    order.payment_status = Order.PAID
                    order.save()

                    # save order and other commission details
                    order.save_vendor_and_commision()
                    
                    # Process referral reward if applicable
                    process_referral_reward(order)

                    trx_extist.status = "completed"
                    trx_extist.response_data = response
                    trx_extist.external_reference = reference
                    trx_extist.description = 'Order Payment'
                    trx_extist.save()

                    # send websocket notification to buyer
                    try:
                        channel_layer = get_channel_layer()
                        # vendor_group_name = f'vendor_85fc6465-b453-4f53-9bef-a43a91d973fe'
                        vendor_group_name = f'vendor_{order.vendor.user.id}'
                        from django.core.serializers.json import DjangoJSONEncoder
                        async_to_sync(channel_layer.group_send)(
                            vendor_group_name,
                            {
                                'type': 'new_order_notification',
                                'data': {
                                    'order_id': str(order.id),
                                    'track_id': str(order.track_id),
                                    'customer': {
                                        'name': order.user.full_name,
                                        'phone': order.user.phone_number
                                    },
                                    "order_details": json.loads(
                                        json.dumps(OrderSerializer(
                                            order).data, cls=DjangoJSONEncoder)
                                    ),
                                    'delivery_address': order.address,
                                    'created_at': order.created_at.isoformat(),
                                    'status': order.status,
                                    'payment_status': order.payment_status,
                                }
                            }
                        )

                    except Exception as e:
                        print(f"WebSocket error: {e}")

                    # Send push notification to vendor about new order
                    try:
                        result = notification_helper.send_to_users_with_executor(
                            users=[order.vendor.user],
                            title="New Order Received!",
                            body=f"New order #{str(order.track_id)} has been placed",
                            data={
                                "event": "new_order",
                                "order_id": str({order.track_id}),
                            }
                        )
                        print(f"Vendor notification result: {result}")
                    except Exception as e:
                        print(f"Vendor notification error: {e}")

                    # Send push notification to customer about payment success
                    try:
                        result = notification_helper.send_to_users_with_executor(
                            users=[order.user],
                            title="Payment Successful!",
                            body=(
                                f"Your payment for Order #{order.track_id} was successful! "
                                f"Delivery code: {order.delivery_otp}."
                            ),
                            data={
                                "event": "payment_success",
                                "order_id": str(order.id),
                                "order_status": order.status,
                                "delivery_code": order.delivery_otp or "",
                            }
                        )
                        print(
                            f"Customer payment notification result: {result}")
                    except Exception as e:
                        print(f"Customer payment notification error: {e}")

                return success_response(
                    message="Transaction processed successfully",
                    data=OrderSerializer(order).data
                )
            failed_order = self._mark_order_payment_failed(
                trx_extist,
                response_payload=response,
                reference=reference,
            )
            return bad_request_response(
                message="Payment failed",
                data=OrderSerializer(failed_order).data if failed_order else None,
            )

        except:
            return bad_request_response(
                message='Transaction not doest exist',
                status_code=404
            )
        return bad_request_response(
            message="Transaction not doest exist"
        )


class OrderPaymentWebhookView(generics.GenericAPIView):
    permission_classes = []

    def post(self, request, id):
        data = request.data
        try:
            reference = data.get('reference')
            trx_extist = WalletTransaction.objects.filter(
                external_reference=reference).first()
            if not trx_extist:
                return bad_request_response(
                    message="Transaction not doest exist"
                )
            metadata = data.get('metadata', {})
            if metadata:
                order = trx_extist.order
                order.payment_status = Order.PAID
                order.save()
                
                # Process referral reward if applicable
                process_referral_reward(order)

                trx_extist.status = "completed"
                trx_extist.response_data = data
                trx_extist.description = 'Order Payment'
                trx_extist.save()
                return success_response(
                    message="Transaction processed successfully"
                )
        except:
            return bad_request_response(
                message='Transaction not doest exist',
                status_code=404
            )


class RiderViewSet(viewsets.ModelViewSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_layer = get_channel_layer()

    queryset = Rider.objects.all()
    serializer_class = RiderSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'accep_order':
            return AcceptOrderSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        user = self.request.user

        # If user is a rider, they can only see their own profile
        if hasattr(user, 'rider'):
            return Rider.objects.filter(user=user)

        # Admin or vendor can see all riders
        return Rider.objects.all()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def update_location(self, request, pk=None):
        rider: Rider = self.get_object()
        serializer = RiderLocationUpdateSerializer(data=request.data)

        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']

            rider.update_location(latitude, longitude)

            self.broadcast_location_update(rider, latitude, longitude)
            return success_response(
                message='Location updated'
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def update_order_status(self, request, pk=None):
        rider = self.get_object()
        order_id = request.data.get('order_id')
        new_status = request.data.get('status')

        try:
            order = Order.objects.get(id=order_id, rider=rider)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found")

        if order.rider != rider:
            return bad_request_response(message="Order not found")

        order_statuses = [choice[0] for choice in Order.ORDER_STATUS_CHOICES]
        delivery_statuses = [choice[0] for choice in Order.DELIVERY_STATUS_CHOICES]
        valid_statuses = sorted(set(order_statuses + delivery_statuses))
        if new_status not in valid_statuses:
            return bad_request_response(
                message=f"Invalid status: '{new_status}'. Must be one of: {', '.join(valid_statuses)}"
            )

        old_status = order.status
        if new_status in order_statuses:
            order.status = new_status
        if new_status in delivery_statuses:
            order.delivery_status = new_status
        elif new_status == 'near_delivery':
            order.delivery_status = 'in_transit'
        order.save()

        # Broadcast status update
        try:
            room_group_name = f'delivery_{order.id}'
            async_to_sync(self.channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'order_status_update',
                    'data': {
                        'order_id': str(order.id),
                        'old_status': old_status,
                        'new_status': new_status,
                        'updated_at': order.updated_at.isoformat(),
                        'rider': {
                            'id': str(rider.id),
                            'name': rider.user.full_name if rider.user else None,
                            'phone': rider.user.phone_number if rider.user else None
                        }
                    }
                }
            )
        except:
            pass

        try:
            customer_group_name = f'customer_{order.user.id}'
            channel_layer = get_channel_layer()
            status_message = {
                'picked_up': 'Your rider has picked up your order.',
                'in_transit': 'Your order is on the way.',
                'near_delivery': 'Your rider is outside and waiting for you.',
                'delivered': 'Your order has been delivered.',
            }.get(order.status, 'Order status updated!')

            async_to_sync(channel_layer.group_send)(
                customer_group_name,
                {
                    'type': 'order_status_update',
                    'data': {
                        'order_id': str(order.id),
                        'status': order.status,
                        'message': status_message
                    }
                }
            )
        except Exception as e:
            print(f"WebSocket notification to customer error: {e}")

        if new_status == 'near_delivery':
            try:
                send_order_status_update_notification(
                    order,
                    'near_delivery',
                    message='Your rider is outside and waiting for you.',
                )
            except Exception as e:
                print(f"Push notification to customer error: {e}")
            try:
                notification_helper.send_to_users_with_executor(
                    users=[order.user],
                    title="Your rider is outside 📍",
                    body="Your rider is outside and waiting for you.",
                    data={
                        "event": "near_delivery",
                        "type": "order_status_update",
                        "order_id": str(order.id),
                        "status": "near_delivery",
                    }
                )
            except Exception as e:
                print(f"Direct near-delivery push error: {e}")

        return success_response(
            message=f'Order status updated to {new_status}',
            data={'order_id': str(order.id), 'status': new_status}
        )

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in kilometers"""
        if not all([lat1, lon1, lat2, lon2]):
            return 0

        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * \
            math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def calculate_eta(self, distance_km):
        """Calculate estimated time of arrival in minutes"""
        print(distance_km)
        if distance_km == 0:
            return 0

        # Assume average speed of 25 km/h for delivery
        average_speed = 25
        eta_hours = distance_km / average_speed
        return int(eta_hours * 60)  # Convert to minutes

    def broadcast_location_update(self, rider, latitude, longitude):
        """Broadcast rider location to all active order tracking rooms"""
        active_orders = rider.orders.filter(
            status__in=['confirmed', 'ready_for_pickup',
                        'picked_up', 'in_transit', 'near_delivery']
        )

        for order in active_orders:
            room_group_name = f'delivery_{order.id}'

            # Calculate distance to customer
            distance_to_customer = self.calculate_distance(
                latitude, longitude,
                float(order.delivery_latitude) if order.delivery_latitude else 0,
                float(order.delivery_longitude) if order.delivery_longitude else 0
            )

            # Update order status if near delivery
            distance_value = distance_to_customer
            if distance_value < 1:
                distance_value = distance_value * 1000
                distance_type = "meter"
            else:
                distance_type = "kilometer"

            # Only mark near delivery when the rider is actually in transit
            # and close enough to the customer's destination.
            if distance_to_customer <= 1.5 and order.status == 'in_transit':
                order.status = 'near_delivery'
                order.save()

                # Send status update
                async_to_sync(self.channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'order_status_update',
                        'data': convert_decimals({
                            'order_id': str(order.id),
                            'status': 'near_delivery',
                            'distance_to_customer': round(distance_value, 3),
                            'distance_to_customer_type': distance_type,
                            'estimated_arrival': self.calculate_eta(distance_value if distance_type == "kilometer" else distance_value / 1000),
                            'estimated_arrival_type': "minutes",
                            'updated_at': order.updated_at.isoformat()
                        })
                    }
                )

                try:
                    customer_group_name = f'customer_{order.user.id}'
                    async_to_sync(self.channel_layer.group_send)(
                        customer_group_name,
                        {
                            'type': 'order_status_update',
                            'data': convert_decimals({
                                'order_id': str(order.id),
                                'status': 'near_delivery',
                                'distance_to_customer': round(distance_value, 3),
                                'distance_to_customer_type': distance_type,
                                'estimated_arrival': self.calculate_eta(distance_value if distance_type == "kilometer" else distance_value / 1000),
                                'estimated_arrival_type': "minutes",
                                'message': 'Your rider is outside and waiting for you.',
                                'updated_at': order.updated_at.isoformat()
                            })
                        }
                    )
                except Exception as e:
                    print(f"WebSocket near-delivery notification to customer error: {e}")

                try:
                    send_order_status_update_notification(
                        order,
                        'near_delivery',
                        message='Your rider is outside and waiting for you.',
                    )
                except Exception as e:
                    print(f"Push near-delivery notification error: {e}")
                try:
                    notification_helper.send_to_users_with_executor(
                        users=[order.user],
                        title="Your rider is outside 📍",
                        body="Your rider is outside and waiting for you.",
                        data={
                            "event": "near_delivery",
                            "type": "order_status_update",
                            "order_id": str(order.id),
                            "status": "near_delivery",
                        }
                    )
                except Exception as e:
                    print(f"Direct broadcast near-delivery push error: {e}")

            try:
                # Send location update
                async_to_sync(self.channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'rider_location_update',
                        'data': convert_decimals({
                            'order_id': str(order.id),
                            'rider_location': {
                                'latitude': latitude,
                                'longitude': longitude,
                                'updated_at': rider.location_updated_at.isoformat()
                            },
                            "rider": {
                                'id': str(rider.id),
                                'name': rider.user.full_name,
                                "email": rider.user.email
                            },
                            'distance_to_customer': round(distance_value, 3),
                            'distance_to_customer_type': distance_type,
                            'estimated_arrival': self.calculate_eta(distance_value if distance_type == "kilometer" else distance_value / 1000),
                            'estimated_arrival_type': "minutes"
                        })
                    }
                )
            except:
                pass

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def request_withdrawal(self, request):
        rider = Rider.objects.filter(user=request.user).first()
        if not rider:
            return bad_request_response(message='Rider profile not found', status_code=404)
        wallet, _ = Wallet.objects.get_or_create(user=rider.user)

        amount = request.data.get('amount')
        if amount is None:
            return bad_request_response(
                message='Amount is required'
            )

        try:
            amount = Decimal(amount)
        except:
            return bad_request_response(
                message='Invalid amount format.'
            )

        if amount <= 0:
            return bad_request_response(
                message='Withdrawal amount must be positive.'
            )

        minimum_amount = get_minimum_withdrawal_for_user(request.user)
        if amount < minimum_amount:
            return bad_request_response(
                message=f'Minimum withdrawal amount is NGN {minimum_amount}.'
            )

        if wallet.balance < amount:
            return bad_request_response(
                message='Insufficient balance.'
            )

        # Create a pending withdrawal transaction
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            user=rider.user,
            amount=amount,
            transaction_type='withdrawal',
            status='pending',
            description='Rider withdrawal request',
        )

        # Optionally update wallet balance here if you deduct immediately,
        # or wait until withdrawal is approved/completed

        return success_response(
            message='Withdrawal request submitted.',
            status_code=201
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def available_order(self, request, pk=None):
        rider = self.get_object()

        query_location_latitude = self.request.GET.get('latitude')
        query_location_longitude = self.request.GET.get('longitude')

        # Determine which location to use (current location or address location)
        if not query_location_latitude or not query_location_longitude:
            rider_lat = rider.current_latitude
            rider_lon = rider.current_longitude

            # Use address location as fallback if current location is not available
            if not rider_lat or not rider_lon:
                rider_lat = rider.location_latitude
                rider_lon = rider.location_longitude
        else:
            rider_lat = query_location_latitude
            rider_lon = query_location_longitude

        # Check if any location is available
        if not rider_lat or not rider_lon:
            return bad_request_response(
                message="Rider location not available. Please update your current location or address."
            )

        declined_order_ids = rider.declined_orders.values_list(
            'order_id', flat=True)

        # Fetch candidate orders with all relations needed by is_order_visible_to_rider
        # and by the serializer — one DB round-trip for the loop, no N+1 after.
        candidate_qs = Order.objects.filter(
            rider=None,
            status__in=['looking_for_rider', 'awaiting_rider'],
        ).exclude(id__in=declined_order_ids).select_related(
            'vendor', 'vendor__user',
        ).prefetch_related(
            'items',
            'items__product',
            'items__product__productimage_set',
        )

        nearby_orders = []
        for order in candidate_qs:
            if is_order_visible_to_rider(
                order,
                rider,
                latitude=float(rider_lat),
                longitude=float(rider_lon),
            ):
                nearby_orders.append(order)

        from django.db.models import Case, When

        order_ids = [order.id for order in nearby_orders]

        preserved_order = Case(
            *[When(id=pk, then=pos) for pos, pk in enumerate(order_ids)]
        )

        queryset = Order.objects.filter(id__in=order_ids).select_related(
            'vendor', 'vendor__user',
        ).prefetch_related(
            'items',
            'items__product',
            'items__product__productimage_set',
        ).order_by(preserved_order).order_by('-created_at')

        return paginate_success_response_with_serializer(
            self.request,
            OrderSerializer,
            queryset,
            page_size=10
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def accept_order(self, request, pk=None):
        rider = self.get_object()

        from product.models import PlatformSettings
        settings = PlatformSettings.get_settings()
        if not settings.is_multi_stop_enabled:
            active_orders = Order.objects.filter(
                rider=rider,
                status__in=['rider_assigned', 'picked_up',
                            'in_transit', 'near_delivery']
            ).exists()
            if active_orders:
                return bad_request_response(message="Multi-stop delivery is disabled. Please complete your current order first.")

        order_id = request.data.get('order_id')
        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .get(id=order_id)
                )

                if order.rider:
                    return bad_request_response(
                        message="Order already assigned to a rider",
                    )

                order.assign_rider(rider)

        except Order.DoesNotExist:
            return bad_request_response(
                message="Order not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        # send push notification to customer about order acceptance
        try:
            result = notification_helper.send_to_users_with_executor(
                users=[order.user],
                title="Order Accepted! ✅",
                body=f"Your order #{str(order.track_id)} has been accepted by a rider and is being prepared for pickup.",
                data={
                    "event": "order_accepted",
                    "order_id": str(order.id),
                    "order_status": order.status,
                    "rider_id": str(rider.id),
                    "rider_name": rider.user.full_name or '',
                    "rider_phone": rider.user.phone_number or '',
                }
            )
            print(f"Customer order acceptance notification result: {result}")
        except Exception as e:
            print(f"Customer order acceptance notification error: {e}")

        try:
            notify_rider_order_assignment(
                order,
                rider,
                message=(
                    f"You have accepted order #{str(order.track_id)}. "
                    "Please proceed to the vendor to pick up the order."
                ),
            )
        except Exception as e:
            print(f"Rider order acceptance notification error: {e}")

        try:
            notify_order_unavailable_to_riders(order, accepted_rider=rider)
        except Exception as e:
            print(f"Other rider cleanup notification error: {e}")


        # send a notification to vendor about order acceptance
        try:
            result = notification_helper.send_to_users_with_executor(
                users=[order.vendor.user],
                title="Order Accepted by Rider! ✅",
                body=f"Your order #{str(order.track_id)} has been accepted by a rider and is being prepared for pickup.",
                data={
                    "event": "order_accepted_by_rider",
                    "order_id": str(order.id)
                }
            )
        except Exception as e:
            print(f"Vendor notification error: {e}")
        # Send WebSocket notification to vendor
        try:
            channel_layer = get_channel_layer()
            vendor_group_name = f'vendor_{order.vendor.user.id}'

            async_to_sync(channel_layer.group_send)(
                vendor_group_name,
                {
                    'type': 'order_accepted_notification',
                    'data': {
                        'order_id': str(order.id),
                        'rider': {
                            'id': rider.id,
                            'name': rider.user.get_full_name(),
                            'phone': rider.user.phone_number,
                        },
                        'accepted_at': order.updated_at.isoformat(),
                        'status': order.status,
                    }
                }
            )
        except Exception as e:
            print("WebSocket error:", e)

        try:
            customer_group_name = f'customer_{order.user.id}'
            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                customer_group_name,
                {
                    'type': 'order_status_update',
                    'data': {
                        'order_id': str(order.id),
                        'status': 'rider_assigned',
                        'message': f'A rider has been assigned to your order #{order.track_id}!',
                        'rider': {
                            'id': str(rider.id),
                            'name': rider.user.full_name,
                            'phone': rider.user.phone_number,
                        },
                    }
                }
            )
        except Exception as e:
            print(f"WebSocket notification to customer error: {e}")

        return success_response(
            message='Order accepted successfully'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def toggle_online_status(self, request, pk=None):
        rider = self.get_object()
        go_online = request.data.get('online', False)

        try:
            if go_online:
                rider.go_online()
                return success_response(
                    message='Rider is now online'
                )
            else:
                rider.go_offline()
                return success_response(
                    message='Rider is now offline'
                )
        except ValueError as exc:
            return bad_request_response(message=str(exc))

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def active_orders(self, request, pk=None):
        rider = self.get_object()
        active_orders = rider.orders.filter(
            status__in=['rider_assigned', 'confirmed', 'ready_for_pickup',
                        'picked_up', 'in_transit', 'near_delivery']
        )
        return paginate_success_response_with_serializer(
            request,
            OrderSerializer,
            active_orders,
            page_size=int(request.GET.get('page', 10)),
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def delivered_orders(self, request, pk=None):
        rider = self.get_object()
        active_orders = rider.orders.filter(
            status__in=['delivered']
        )
        return paginate_success_response_with_serializer(
            request,
            OrderSerializer,
            active_orders,
            page_size=int(request.GET.get('page', 10)),
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated], url_path='pick_up_orders')
    def picked_up_orders(self, request, pk=None):
        rider = self.get_object()
        active_orders = rider.orders.filter(
            status__in=['picked_up', 'near_delivery']
        )
        return paginate_success_response_with_serializer(
            request,
            OrderSerializer,
            active_orders,
            page_size=int(request.GET.get('page', 10)),
        )
        # return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def decline_order(self, request, pk=None):
        rider = self.get_object()
        order_id = request.data.get('order_id')

        if not order_id:
            return bad_request_response(message="Order ID is required")

        try:
            order = Order.objects.get(id=order_id, rider=None)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found or already assigned")

        # Mark as declined
        DeclinedOrder.objects.get_or_create(rider=rider, order=order)

        return success_response(
            message="Order declined successfully",
            data={"order_id": str(order.id)}
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def reviews(self, request, pk=None):
        rider = self.get_object()
        reviews = RiderRating.objects.filter(
            rider=rider).order_by('-created_at')
        return paginate_success_response_with_serializer(
            request,
            RiderRatingCreateSerializer,
            reviews,
            page_size=10
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def analytics(self, request, pk=None):
        rider = self.get_object()

        orders = Order.objects.filter(rider=rider)
        delivered_orders = orders.filter(status='delivered')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        if date_from:
            parsed_from = parse_date(date_from)
            if parsed_from:
                orders = orders.filter(created_at__date__gte=parsed_from)
                delivered_orders = delivered_orders.filter(
                    delivered_at__date__gte=parsed_from
                )

        if date_to:
            parsed_to = parse_date(date_to)
            if parsed_to:
                orders = orders.filter(created_at__date__lte=parsed_to)
                delivered_orders = delivered_orders.filter(
                    delivered_at__date__lte=parsed_to
                )

        total_orders = orders.count()
        total_earnings = delivered_orders.aggregate(
            total=Sum('rider_earning')
        )['total'] or 0
        total_pending_delivery = orders.filter(
            status__in=['rider_assigned', 'confirmed', 'picked_up', 'in_transit', 'near_delivery']
        ).count()
        total_completed_delivery = delivered_orders.count()
        total_rejected_delivery = 0
        response = {
            'total_orders': total_orders,
            'total_earnings': total_earnings,
            'total_pending_delivery': total_pending_delivery,
            'total_completed_delivery': total_completed_delivery,
            'total_rejected_delivery': total_rejected_delivery,

        }

        return success_response(
            data=response
        )

    def _complete_delivery(self, order: Order, rider: Rider):
        from helpers.order_utils import calculate_rider_fare, get_distance_between_two_location
        from wallet.models import Wallet, WalletTransaction
        from decimal import Decimal

        order.status = 'delivered'
        order.delivery_status = 'delivered'
        order.delivery_otp = None
        order.delivery_otp_expiry = None
        order.delivered_at = timezone.now()

        gross_order_amount = order.calculate_vendor_settlement_amount()
        if gross_order_amount <= 0:
            gross_order_amount = Decimal(str(order.vendor_amount or 0))

        order.vendor_amount = gross_order_amount
        order.platform_amount = max(
            Decimal('0.00'),
            Decimal(str(order.get_total_price() or 0)) - gross_order_amount,
        )

        # update vendor wallet and create transaction record for vendor earning
        vendor_wallet, _ = Wallet.objects.get_or_create(user=order.vendor.user)
        vendor_earning = order.vendor_amount or Decimal('0.00')
        vendor_wallet.deposit(vendor_earning)

        WalletTransaction.objects.create(
            wallet=vendor_wallet,
            user=order.vendor.user,
            amount=vendor_earning,
            transaction_type='earning',
            status='completed',
            description=f"Earning from Order #{order.track_id}",
            order=order
        )

        gross_earning_amount = order.calculate_rider_earning_amount()
        try:
            dist = 0.5
            vendor_lat = getattr(order.vendor, 'location_latitude', None)
            vendor_lng = getattr(order.vendor, 'location_longitude', None)
            user_address = getattr(order, 'user_address', None)
            if vendor_lat and vendor_lng and user_address:
                dist = get_distance_between_two_location(
                    float(vendor_lat),
                    float(vendor_lng),
                    float(user_address.latitude),
                    float(user_address.longitude)
                ) or 0.5
            gross_earning_amount = max(
                order.calculate_rider_earning_amount(),
                Decimal(str(calculate_rider_fare(dist))),
            )
        except Exception as earning_error:
            print(f"Error calculating rider earning for {order.track_id}: {earning_error}")

        # Apply platform commission to get net amount credited to rider
        rider_earning_amount = order.calculate_net_rider_earning(gross_earning_amount)
        order.rider_earning = rider_earning_amount

        try:
            wallet, _ = Wallet.objects.get_or_create(user=rider.user)
            wallet.deposit(rider_earning_amount)

            WalletTransaction.objects.create(
                wallet=wallet,
                user=rider.user,
                amount=rider_earning_amount,
                transaction_type='earning',
                status='completed',
                description=f"Earning from Order #{order.track_id}",
                order=order
            )
        except Exception as earning_error:
            print(f"Error recording rider earning for {order.track_id}: {earning_error}")

        order.save()

        # send push notification to rider about delivery confirmation
        try:
            notification_helper.send_to_users_with_executor(
                users=[rider.user],
                title="Delivery Confirmed! 🎉",
                body=f"Order #{order.track_id} has been marked as delivered. Your earnings have been updated.",
                data={
                    "event": "delivery_confirmed",
                    "order_id": str(order.id),
                    "rider_earning": str(order.rider_earning)
                }
            )
        except Exception as e:
            print(f"Rider delivery confirmation notification error: {e}")

        # send push notification to customer about delivery confirmation
        try:
            notification_helper.send_to_users_with_executor(
                users=[order.user],
                title="Your Order has been Delivered! 🎉",
                body=f"Order #{order.track_id} has been delivered. Thank you for using our service!",
                data={
                    "event": "order_delivered",
                    "type": "order_status_update",
                    "order_id": str(order.id),
                    "status": "delivered",
                    "delivery_status": "delivered",
                }
            )
        except Exception as e:
            print(f"Customer delivery confirmation notification error: {e}")

        # send push notification to vendor about delivery confirmation
        try:
            notification_helper.send_to_users_with_executor(
                users=[order.vendor.user],
                title="Order has been delivered ✅",
                body=f"Order #{order.track_id} has been delivered.",
                data={
                    "event": "order_delivered",
                    "order_id": str(order.id),
                    "order_status": "delivered"
                }
            )
        except Exception:
            print()

        try:
            channel_layer = get_channel_layer()
            vendor_group_name = f'vendor_{order.vendor.user.id}'
            async_to_sync(channel_layer.group_send)(
                vendor_group_name,
                {
                    'type': 'order_delivered_notification',
                    'data': {
                        'order_id': str(order.id),
                        'status': order.status,
                        'delivered_at': order.delivered_at.isoformat(),
                        'rider': {
                            'id': rider.id,
                            'name': rider.user.get_full_name(),
                            'phone': rider.user.phone_number
                        }
                    }
                }
            )
        except Exception as e:
            print("WebSocket error:", e)

        try:
            channel_layer = get_channel_layer()
            customer_group_name = f'customer_{order.user.id}'
            async_to_sync(channel_layer.group_send)(
                customer_group_name,
                {
                    'type': 'order_status_update',
                    'data': {
                        'order_id': str(order.id),
                        'track_id': str(order.track_id),
                        'status': 'delivered',
                        'delivery_status': 'delivered',
                        'delivered_at': order.delivered_at.isoformat(),
                        'message': 'Your order has been delivered. Enjoy your meal!',
                    }
                }
            )
        except Exception as e:
            print("Customer WebSocket notification error:", e)

        try:
            channel_layer = get_channel_layer()
            rider_group_name = f'riders_group_{rider.user.id}'
            async_to_sync(channel_layer.group_send)(
                rider_group_name,
                {
                    'type': 'order_delivered_notification',
                    'data': {
                        'order_id': str(order.id),
                        'track_id': str(order.track_id),
                        'status': 'delivered',
                        'delivered_at': order.delivered_at.isoformat(),
                        'rider_earning': float(order.rider_earning) if order.rider_earning else 0,
                        'message': 'Order delivered successfully. Your earnings have been updated.',
                    }
                }
            )
        except Exception as e:
            print("Rider WebSocket notification error:", e)

        return success_response(message="Delivery code verification successful")

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def send_delivery_otp(self, request, pk=None):
        rider = self.get_object()
        order_id = request.data.get('order_id')
        if not order_id:
            return bad_request_response(
                message='Order id is required'
            )

        #
        # Fetch order assigned to this rider
        order = Order.objects.filter(id=order_id, rider=rider).first()
        if not order:
            return bad_request_response(
                message='Order not found or not assigned to you',
                status_code=404
            )

        if order.delivery_otp != request.data.get('code'):
            return bad_request_response(
                message="Invalid delivery code"
            )
        return self._complete_delivery(order, rider)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def confirm_delivery(self, request, pk=None):
        rider: Rider = self.get_object()
        order_id = request.data.get('order_id')
        otp = request.data.get('otp')

        order: Order = Order.objects.filter(id=order_id, rider=rider).first()
        if not order:
            return bad_request_response(
                message='Order not found or not assigned to you',
            )

        # if not order.delivery_otp or timezone.now() > order.delivery_otp_expiry:
        #     return bad_request_response(
        #         message='OTP expired or not found',

        #     )

        if otp != order.delivery_otp:
            return bad_request_response(
                message='Invalid OTP',
            )

        return self._complete_delivery(order, rider)


def convert_decimals(obj):
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


class EnhancedRiderViewSet(viewsets.ModelViewSet):
    queryset = Rider.objects.all()
    serializer_class = RiderSerializer
    permission_classes = []
    # permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_layer = get_channel_layer()

    @action(detail=True, methods=['post'], permission_classes=[])
    # @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def update_location(self, request, pk=None):
        rider = self.get_object()
        serializer = RiderLocationUpdateSerializer(data=request.data)

        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']

            # Update rider location
            rider.update_location(latitude, longitude)

            # Broadcast location update to all active orders
            self.broadcast_location_update(rider, latitude, longitude)

            return success_response(
                message='Location updated and broadcasted',
                data={
                    'latitude': latitude,
                    'longitude': longitude,
                    'updated_at': rider.location_updated_at.isoformat()
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def broadcast_location_update(self, rider, latitude, longitude):
        """Broadcast rider location to all active order tracking rooms"""
        active_orders = rider.orders.filter(
            status__in=['confirmed', 'ready_for_pickup',
                        'picked_up', 'in_transit', 'near_delivery']
        )

        for order in active_orders:
            room_group_name = f'delivery_{order.id}'

            # Calculate distance to customer
            distance_to_customer = self.calculate_distance(
                latitude, longitude,
                float(order.delivery_latitude) if order.delivery_latitude else 0,
                float(order.delivery_longitude) if order.delivery_longitude else 0
            )

            # Update order status if near delivery
            distance_value = distance_to_customer
            if distance_value < 1:
                distance_value = distance_value * 1000
                distance_type = "meter"
            else:
                distance_type = "kilometer"

            if distance_to_customer <= 1.5 and order.status == 'in_transit':
                order.status = 'near_delivery'
                order.save()

                # Send status update
                async_to_sync(self.channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'order_status_update',
                        'data': convert_decimals({
                            'order_id': str(order.id),
                            'status': 'near_delivery',
                            'distance_to_customer': round(distance_value, 3),
                            'distance_to_customer_type': distance_type,
                            'estimated_arrival': self.calculate_eta(distance_value if distance_type == "kilometer" else distance_value / 1000),
                            'estimated_arrival_type': "minutes",
                            'updated_at': order.updated_at.isoformat()
                        })
                    }
                )

            # Send location update
            async_to_sync(self.channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'rider_location_update',
                    'data': convert_decimals({
                        'order_id': str(order.id),
                        'rider_location': {
                            'latitude': latitude,
                            'longitude': longitude,
                            'updated_at': rider.location_updated_at.isoformat()
                        },
                        "rider": {
                            'id': rider.id,
                            'name': rider.user.full_name,
                            "email": rider.user.email
                        },
                        'distance_to_customer': round(distance_value, 3),
                        'distance_to_customer_type': distance_type,
                        'estimated_arrival': self.calculate_eta(distance_value if distance_type == "kilometer" else distance_value / 1000),
                        'estimated_arrival_type': "minutes"
                    })
                }
            )

    @action(detail=True, methods=['post'])
    def update_order_status(self, request, pk=None):
        rider = self.get_object()
        order_id = request.data.get('order_id')
        new_status = request.data.get('status')

        try:
            order = Order.objects.get(id=order_id, rider=rider)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found")

        # Update order status
        old_status = order.status
        order.status = new_status
        order.save()

        # Broadcast status update
        room_group_name = f'delivery_{order.id}'
        async_to_sync(self.channel_layer.group_send)(
            room_group_name,
            {
                'type': 'order_status_update',
                'data': {
                    'order_id': str(order.id),
                    'old_status': old_status,
                    'new_status': new_status,
                    'updated_at': order.updated_at.isoformat(),
                    'rider': {
                        'id': str(rider.id),
                        'name': rider.user.full_name if rider.user else None,
                        'phone': rider.user.phone_number if rider.user else None
                    }
                }
            }
        )

        return success_response(
            message=f'Order status updated to {new_status}',
            data={'order_id': str(order.id), 'status': new_status}
        )

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in kilometers"""
        if not all([lat1, lon1, lat2, lon2]):
            return 0

        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * \
            math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c


class WebSocketSimulationView(generics.GenericAPIView):
    permission_classes = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_layer = get_channel_layer()

    def post(self, request):
        """
        Endpoint to simulate WebSocket events for testing purposes.
        """
        event_type = request.data.get('event_type')
        order_id = request.data.get('order_id')

        if not event_type or not order_id:
            return bad_request_response(
                message="Both event_type and order_id are required"
            )

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return bad_request_response(
                message="Order not found",
                status_code=404
            )

        # Define different event types and their corresponding WebSocket messages
        event_handlers = {
            'order_status_update': self._handle_order_status_update,
            'rider_location_update': self._handle_rider_location_update,
            'rider_accepted': self._handle_rider_accepted,
            'order_delivered': self._handle_order_delivered,
            'near_delivery': self._handle_near_delivery
        }

        if event_type not in event_handlers:
            return bad_request_response(
                message=f"Invalid event type. Must be one of: {', '.join(event_handlers.keys())}"
            )

        # Call the appropriate handler
        result = event_handlers[event_type](request, order)

        return success_response(
            message=f"WebSocket event '{event_type}' simulated successfully",
            data=result
        )

    def _handle_order_status_update(self, request, order):
        """Handle order status update event"""
        status = request.data.get('status', 'in_transit')
        room_group_name = f'delivery_{order.id}'

        data = {
            'order_id': str(order.id),
            'old_status': order.delivery_status,
            'new_status': status,
            'updated_at': timezone.now().isoformat(),
        }

        if order.rider:
            data['rider'] = {
                'id': str(order.rider.id),
                'name': order.rider.user.full_name if order.rider.user else None,
                'phone': order.rider.user.phone_number if order.rider.user else None
            }

        async_to_sync(self.channel_layer.group_send)(
            room_group_name,
            {
                'type': 'order_status_update',
                'data': data
            }
        )

        return data

    def _handle_rider_location_update(self, request, order):
        """Handle rider location update event"""
        latitude = float(request.data.get('latitude', 0))
        longitude = float(request.data.get('longitude', 0))
        room_group_name = f'delivery_{order.id}'

        data = {
            'order_id': str(order.id),
            'rider_location': {
                'latitude': latitude,
                'longitude': longitude,
                'timestamp': timezone.now().isoformat()
            }
        }

        async_to_sync(self.channel_layer.group_send)(
            room_group_name,
            {
                'type': 'rider_location_update',
                'data': data
            }
        )

        return data

    def _handle_rider_accepted(self, request, order):
        """Handle rider accepted order event"""
        if not order.rider:
            return {"error": "No rider assigned to this order"}

        rider = order.rider
        vendor_group_name = f'vendor_{order.vendor.user.id}'

        data = {
            'order_id': str(order.id),
            'rider': {
                'id': str(rider.id),
                'name': rider.user.get_full_name() if rider.user else "Test Rider",
                'phone': rider.user.phone_number if rider.user else "1234567890"
            },
            'accepted_at': timezone.now().isoformat(),
            'status': order.status
        }

        async_to_sync(self.channel_layer.group_send)(
            vendor_group_name,
            {
                'type': 'order_accepted_notification',
                'data': data
            }
        )

        return data

    def _handle_order_delivered(self, request, order):
        """Handle order delivered event"""
        if not order.rider:
            return {"error": "No rider assigned to this order"}

        rider = order.rider
        vendor_group_name = f'vendor_{order.vendor.user.id}'

        data = {
            'order_id': str(order.id),
            'status': 'delivered',
            'delivered_at': timezone.now().isoformat(),
            'rider': {
                'id': str(rider.id),
                'name': rider.user.get_full_name() if rider.user else "Test Rider",
                'phone': rider.user.phone_number if rider.user else "1234567890"
            }
        }

        async_to_sync(self.channel_layer.group_send)(
            vendor_group_name,
            {
                'type': 'order_delivered_notification',
                'data': data
            }
        )

        return data

    def _handle_near_delivery(self, request, order):
        """Handle near delivery event"""
        room_group_name = f'delivery_{order.id}'

        data = {
            'order_id': str(order.id),
            'status': 'near_delivery',
            'updated_at': timezone.now().isoformat(),
            'message': 'Rider is near your delivery location!'
        }

        async_to_sync(self.channel_layer.group_send)(
            room_group_name,
            {
                'type': 'order_status_update',
                'data': data
            }
        )

        return data

    def calculate_eta(self, distance_km):
        """Calculate estimated time of arrival in minutes"""
        print(distance_km)
        if distance_km == 0:
            return 0

        # Assume average speed of 25 km/h for delivery
        average_speed = 25
        eta_hours = distance_km / average_speed
        return int(eta_hours * 60)  # Convert to minutes


class RiderOrderDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = (
                Order.objects
                .select_related('vendor__user', 'user')
                .prefetch_related(
                    'items__product__productimage_set',
                    'items__variant_selections',
                )
                .get(id=order_id)
            )
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.", status_code=404)

        from .serializers import RiderOrderDetailSerializer
        serializer = RiderOrderDetailSerializer(order)
        return success_response(data=serializer.data)


class RiderRatingCreateView(generics.CreateAPIView):
    """View for creating vendor ratings"""
    serializer_class = RiderRatingCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


class UploadRiderDocumentView(generics.GenericAPIView):
    serializer_class = RiderDocumentUploadSerializer
    permission_classes = [IsAuthenticated]

    # @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])

    def patch(self, request, id):
        """
        Upload multiple rider documents and extra info in a single request
        """
        from account.models import Guarantor
        serializer = RiderDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(message='Rider not found', status_code=404)

        # Update extra fields
        for field in [
                'vehicle_brand', 'plate_number', 'next_of_kin', 'next_of_kin_phone', 'preferred_location']:
            value = serializer.validated_data.get(field)
            if value is not None:
                setattr(rider, field, value)

        # Handle mode_of_transport
        mode_of_transport = request.data.get('mode_of_transport')
        valid_transport_keys = [choice[0] for choice in MODE_OF_TRANSPORTATION]
        if mode_of_transport not in valid_transport_keys:
            return bad_request_response(message='Invalid mode of transport', status_code=400)
        rider.mode_of_transport = mode_of_transport

        # Save document images
        field_mapping = {
            'license_front': 'drivers_license_front',
            'license_back': 'drivers_license_back',
            'nin_front': 'nin_front',
            'nin_back': 'nin_back',
            'profile_photo': 'profile_photo'
        }
        uploaded_documents = []
        failed_documents = []
        if request.FILES:
            for doc_type, field_name in field_mapping.items():
                if doc_type in request.FILES:
                    image_file = request.FILES[doc_type]
                    if image_file.size > 5 * 1024 * 1024:
                        failed_documents.append({
                            'document_type': doc_type,
                            'reason': 'Image size exceeds 5MB limit'
                        })
                        continue
                    try:
                        if doc_type == 'profile_photo':
                            from helpers.backblaze import upload_to_backblaze
                            import uuid, os
                            ext = os.path.splitext(image_file.name)[1]
                            filename = f"rider_profiles/{rider.user.id}_{uuid.uuid4()}{ext}"
                            upload_result = upload_to_backblaze(image_file, filename)
                            if upload_result and upload_result.get('downloadUrl'):
                                rider.user.profile_image_url = upload_result['downloadUrl']
                            else:
                                failed_documents.append({
                                    'document_type': doc_type,
                                    'reason': 'Failed to upload profile photo'
                                })
                        else:
                            setattr(rider, field_name, image_file)
                            uploaded_documents.append(doc_type)
                    except Exception as e:
                        failed_documents.append({
                            'document_type': doc_type,
                            'reason': 'Error processing file'
                        })

        # Save rider and user
        rider.save()
        if hasattr(rider, 'user'):
            rider.user.save()

        # Handle Guarantors (replace all for this rider)
        
        guarantors_data = serializer.validated_data.get('guarantors', [])
        
        if guarantors_data and isinstance(guarantors_data, list):
            Guarantor.objects.filter(rider=rider).delete()
            for g in guarantors_data:
                Guarantor.objects.create(
                    rider=rider,
                    name=g['name'],
                    phone_number=g['phone_number'],
                    relationship=g.get('relationship', '')
                )

        # Document status logic
        required_fields = ['drivers_license_front',
                           'nin_front', 'drivers_license_back', 'nin_back']
        all_documents_uploaded = all(getattr(rider, field)
                                     for field in required_fields)
        if all_documents_uploaded and rider.status == 'inactive':
            rider.status = 'pending_verification'
            rider.save()
        if rider.document_status != 'approved':
            rider.document_status = 'submitted'
            rider.save()

        rider.refresh_from_db()
        if rider.drivers_license_front and rider.nin_front:
            rider.document_status = 'submitted'
            rider.save()

        return Response({
            'success': len(uploaded_documents) > 0 or not request.FILES,
            'uploaded_documents': [doc.replace('_', ' ').title() for doc in uploaded_documents],
            'failed_documents': failed_documents,
            'verification_status': rider.status
        }, status=status.HTTP_200_OK if uploaded_documents or not request.FILES else status.HTTP_400_BAD_REQUEST)


class RiderGuarantorUpdateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        guarantors = request.data.get('guarantors', [])
        if not isinstance(guarantors, list) or not guarantors:
            return bad_request_response(message='Guarantors list required', status_code=400)
        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(message='Rider not found', status_code=404)
        # Remove old guarantors
        
        # Add new ones
        if guarantors and isinstance(guarantors, list):
            Guarantor.objects.filter(rider=rider).delete()
            for g in guarantors:
                Guarantor.objects.create(
                    rider=rider,
                    name=g.get('name'),
                    phone_number=g.get('phone_number'),
                    relationship=g.get('relationship', '')
                )
        return success_response(message='Guarantor details updated')


class OrderTrackingDetailView(generics.RetrieveAPIView):
    permission_classes = []  # Allow public access with order ID

    def get(self, request, order_id):
        try:
            order = Order.objects.select_related(
                'rider', 'customer', 'vendor').get(id=order_id)

            # Get tracking data
            tracking = DeliveryTracking.objects.filter(order=order).last()

            response_data = {
                'order_id': str(order.id),
                'status': order.status,
                'customer_location': {
                    'latitude': float(order.delivery_latitude) if order.delivery_latitude else None,
                    'longitude': float(order.delivery_longitude) if order.delivery_longitude else None,
                    'address': order.delivery_address
                },
                'vendor_location': {
                    'latitude': float(order.vendor.location_latitude) if order.vendor.location_latitude else None,
                    'longitude': float(order.vendor.location_longitude) if order.vendor.location_longitude else None,
                    'address': order.vendor.address,
                    'name': order.vendor.name
                },
                'rider': {
                    'name': order.rider.user.full_name if order.rider else None,
                    'phone': order.rider.user.phone_number if order.rider else None,
                    'current_location': {
                        'latitude': float(order.rider.current_latitude) if order.rider and order.rider.current_latitude else None,
                        'longitude': float(order.rider.current_longitude) if order.rider and order.rider.current_longitude else None,
                        'updated_at': order.rider.location_updated_at.isoformat() if order.rider and order.rider.location_updated_at else None
                    }
                } if order.rider else None,
                'estimated_delivery_time': tracking.estimated_delivery_time.isoformat() if tracking and tracking.estimated_delivery_time else None,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat()
            }

            return success_response(data=response_data)

        except Order.DoesNotExist:
            return bad_request_response(message="Order not found", status_code=404)


class NearbyRidersView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        radius_km = request.data.get('radius', 5)  # Default 5km radius

        if not latitude or not longitude:
            return bad_request_response(message="Latitude and longitude required")

        # Find nearby online riders
        nearby_riders = []
        online_riders = Rider.objects.filter(
            is_online=True,
            status='active',
            current_latitude__isnull=False,
            current_longitude__isnull=False
        )

        for rider in online_riders:
            distance = self.calculate_distance(
                float(latitude), float(longitude),
                float(rider.current_latitude), float(rider.current_longitude)
            )

            if distance <= radius_km:
                nearby_riders.append({
                    'rider_id': str(rider.id),
                    'name': rider.user.full_name,
                    'location': {
                        'latitude': float(rider.current_latitude),
                        'longitude': float(rider.current_longitude),
                        'updated_at': rider.location_updated_at.isoformat() if rider.location_updated_at else None
                    },
                    'distance_km': round(distance, 2),
                    'active_orders': rider.active_orders_count
                })

        # Sort by distance
        nearby_riders.sort(key=lambda x: x['distance_km'])

        return success_response(
            data={
                'riders': nearby_riders,
                'total_count': len(nearby_riders)
            }
        )

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in kilometers"""
        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * \
            math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c
