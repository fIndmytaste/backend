# views.py
import math
import random
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from account.models import Rider , RiderRating, User
from helpers.paystack import PaystackManager
from helpers.response.response_format import success_response, bad_request_response, internal_server_error_response, paginate_success_response_with_serializer
from product.models import DeliveryTracking, Order
from wallet.models import Wallet, WalletTransaction 
from .serializers import (
    AcceptOrderSerializer,
    OrderSerializer,
    RiderDocumentUploadSerializer,
    RiderRatingCreateSerializer, 
    RiderSerializer, 
    DeliveryTrackingSerializer,
    RiderLocationUpdateSerializer
)
from decimal import Decimal
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter orders based on user role
        if hasattr(user, 'rider'):
            # If user is a rider, show assigned orders
            return Order.objects.filter(rider=user.rider)
        elif hasattr(user, 'vendor'):
            # If user is a vendor, show their orders
            return Order.objects.filter(vendor=user.vendor)
        else:
            # Regular customer sees their own orders
            return Order.objects.filter(user=user)
    
    @action(detail=True, methods=['post'])
    def assign_rider(self, request, pk=None):
        order = self.get_object()
        rider_id = request.data.get('rider_id')
        
        if not rider_id:
            return Response({'error': 'Rider ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            rider = Rider.objects.get(id=rider_id)
            order.assign_rider(rider)
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

        user:User = request.user
        wallet, _ = Wallet.objects.get_or_create(user=user)
        

        order_total_price = order.get_total_price() + order.delivery_fee + order.service_fee
        
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

    def post(self, request): 
        data = request.data
        try:
            reference = data.get('reference')
            
            

            # verify transaction with paytsack
            klass = PaystackManager()
            success , response = klass.verify_transaction(reference)
            if not success:
                print(response)
                return bad_request_response(
                    message="Transaction not doest exist"
                )
            
            
            metadata = response.get('data',{}).get('metadata',{})
            if not metadata:
                return bad_request_response(
                    message="Transaction not doest exist"
                )
            
            transaction_ref = metadata.get('reference')

            try:

                trx_extist = WalletTransaction.objects.get(id=transaction_ref)
            except:
                return bad_request_response(
                    message="Transaction not doest exist"
                )

            if trx_extist.external_reference != reference:
                return bad_request_response(
                    message="Transaction not doest exist"
                )
            
            
            if response['data'].get('status') == 'success':
                #  confirm the amount paid
                amount_paid = (response['data']['amount']) / 100
                print(amount_paid)
                print(amount_paid)
                print(amount_paid)
                if float(amount_paid) != float(trx_extist.amount):
                    return bad_request_response(
                        message="Transaction not doest exist. Amount paid does not match"
                    )
                
                if trx_extist.status == 'pending':
                    order = trx_extist.order
                    order.payment_status = Order.PAID
                    order.save()
                    trx_extist.status = "completed"
                    trx_extist.response_data=response
                    trx_extist.description = 'Order Payment'
                    trx_extist.save()

                    # send websocket notification to buyer
                    try:
                        channel_layer = get_channel_layer()
                        vendor_group_name = f'vendor_{order.vendor.user.id}'

                        async_to_sync(channel_layer.group_send)(
                            vendor_group_name,
                            {
                                'type': 'new_order_notification',
                                'data': {
                                    'order_id': str(order.id),
                                    'customer': {
                                        'name': order.user.full_name,
                                        'phone': order.user.phone_number
                                    },
                                    'delivery_address': order.address,
                                    'created_at': order.created_at.isoformat(),
                                    'status': order.status,
                                    'payment_status': order.payment_status,
                                }
                            }
                        )

                    except Exception as e:
                        print(e)

                return success_response(
                    message="Transaction processed successfully"
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
            trx_extist = WalletTransaction.objects.filter(external_reference=reference).first()
            if not trx_extist:
                return bad_request_response(
                    message="Transaction not doest exist"
                )
            metadata = data.get('metadata',{})
            if metadata:
                order = trx_extist.order
                order.payment_status = Order.PAID
                order.save()
                trx_extist.status = "completed"
                trx_extist.response_data=data
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
        rider = self.get_object()
        serializer = RiderLocationUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']
            
            rider.update_location(latitude, longitude)
            return success_response(
                message='Location updated'
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def request_withdrawal(self, request):

        rider = self.get_object()
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

        if wallet.balance < amount:
            return bad_request_response(
                message='Insufficient balance.'
            )

        # Create a pending withdrawal transaction
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
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
        querset = Order.objects.filter(rider=None, status='pending')
        
        return paginate_success_response_with_serializer(
            self.request,
            OrderSerializer,
            querset,
            page_size=10
        )
    


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def accept_order(self, request, pk=None):
        rider = self.get_object()

        order_id = request.data.get('order_id')
        try:
            order = Order.objects.get(id=order_id)

        except Order.DoesNotExist:
            return bad_request_response(
                message="Order not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        order.assign_rider(rider)
        return success_response(
            message='Order accepted successfully'
        )
       
        

    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def toggle_online_status(self, request, pk=None):
        rider = self.get_object()
        go_online = request.data.get('online', False)
        
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
    


    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def active_orders(self, request, pk=None):
        rider = self.get_object()
        active_orders = rider.orders.filter(
            status__in=['confirmed', 'ready_for_pickup', 'picked_up', 'in_transit', 'near_delivery']
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
    

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def picked_up_orders(self, request, pk=None):
        rider = self.get_object()
        active_orders = rider.orders.filter(
            status__in=['picked_up']
        )
        return paginate_success_response_with_serializer(
            request,
            OrderSerializer,
            active_orders,
            page_size=int(request.GET.get('page', 10)),
        )
        # return Response(serializer.data)

    # @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    # def order_detail(self, request, pk=None):
    #     rider = self.get_object()
    #     order_id = request.query_params.get('order_id')

    #     if not order_id:
    #         return bad_request_response(message='Order ID is required.')

    #     try:order = Order.objects.get(id=order_id)
    #     except:return bad_request_response(message='Invalid Order ID.')
        

    #     serializer = OrderSerializer(
    #         order,
    #         context={
    #             'request': request,
    #             'addition_serializer_data':{
    #                 'rider_order_details':True
    #             }
    #         }
    #     )
    #     return success_response(data=serializer.data)
    

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def reviews(self, request, pk=None):
        rider = self.get_object()
        reviews = RiderRating.objects.filter(rider=rider).order_by('-created_at')
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
        total_orders = orders.count()
        total_earnings = 0
        # total_earnings = orders.aggregate(Sum('total_cost'))['total_cost__sum']
        total_pending_delivery = orders.filter(status__in=['picked_up','in_transit']).count()
        total_completed_delivery = orders.filter(status__in=['delivered']).count()
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
        
        # if order.status not in ['in_transit', 'near_delivery']:
        #     return Response({'error': 'Order not in deliverable status'}, status=400)

        # Generate OTP
        otp = random.randint(10000, 99999)
        order.delivery_otp = str(otp)
        order.delivery_otp_expiry = timezone.now() + timedelta(minutes=10)
        order.save()

        # TODO: Send OTP to customer (SMS/Email)
        # send_otp_to_customer(order.customer, otp)

        return success_response(message=f'OTP sent: {otp}')


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def confirm_delivery(self, request, pk=None):
        rider = self.get_object()
        order_id = request.data.get('order_id')
        otp = request.data.get('otp')

        order:Order = Order.objects.filter(id=order_id, rider=rider).first()
        if not order:
            return bad_request_response(
                message='Order not found or not assigned to you',
            )

        if not order.delivery_otp or timezone.now() > order.delivery_otp_expiry:
            return bad_request_response(
                message='OTP expired or not found',

            )

        if otp != order.delivery_otp:
            return bad_request_response(
                message='Invalid OTP',
            )

        order.status = 'delivered'
        order.delivery_otp = None
        order.delivery_otp_expiry = None
        order.delivered_at = timezone.now()
        order.save()

        return success_response(
            message='Order delivered successfully',
        )




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
            status__in=['confirmed', 'ready_for_pickup', 'picked_up', 'in_transit', 'near_delivery']
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
            if distance_to_customer <= 0.5 and order.status == 'in_transit':  # 500m threshold
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
                        'distance_to_customer': distance_to_customer,
                        'estimated_arrival': self.calculate_eta(distance_to_customer)
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
        
        # Validate status transition
        valid_transitions = {
            'confirmed': ['ready_for_pickup'],
            'ready_for_pickup': ['picked_up'],
            'picked_up': ['in_transit'],
            'in_transit': ['near_delivery'],
            'near_delivery': ['delivered']
        }
        # print(order.status)
        # print(order.status)
        # print(new_status)
        # print(new_status)
        # if new_status not in valid_transitions.get(order.status, []):
        #     return bad_request_response(message="Invalid status transition")
        
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
                        'name': rider.user.full_name,
                        'phone': rider.user.phone_number
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
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    def calculate_eta(self, distance_km):
        """Calculate estimated time of arrival in minutes"""
        if distance_km <= 0:
            return 0
        
        # Assume average speed of 25 km/h for delivery
        average_speed = 25
        eta_hours = distance_km / average_speed
        return int(eta_hours * 60)  # Convert to minutes




class RiderOrderDetailView(generics.GenericAPIView):
    # permission_classes = [IsAuthenticated]
    permission_classes = []

    def get(self, request, order_id):
        # user = request.user

        # if not hasattr(user, 'rider'):
        #     return bad_request_response(message="You are not a rider.")

        # rider = user.rider

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found or not assigned to you.", status_code=404)

        serializer = OrderSerializer(
            order,
            context={
                'request': request,
                'addition_serializer_data': {
                    'rider_order_details': True
                }
            }
        )
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
        Upload multiple rider documents in a single request
        """

        serializer = RiderDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            rider = Rider.objects.get(id=id)
        except Rider.DoesNotExist:
            return bad_request_response(message= 'Rider not found',status_code=404)


        
        # Define field mappings
        field_mapping = {
            'license_front': 'drivers_license_front',
            'license_back': 'drivers_license_back',
            'vehicle_registration': 'vehicle_registration',
            'vehicle_insurance': 'vehicle_insurance',
            'profile_photo': 'profile_photo'
        }
        
        # Track successfully uploaded documents
        uploaded_documents = []
        failed_documents = []
        
        # Check if any files were provided
        if not request.FILES:
            return bad_request_response(message='No files provided')
        
        # Process each file in the request
        for doc_type, field_name in field_mapping.items():
            if doc_type in request.FILES:
                image_file = request.FILES[doc_type]
                
                # Handle file size validation
                if image_file.size > 5 * 1024 * 1024:  # 5MB limit
                    failed_documents.append({
                        'document_type': doc_type,
                        'reason': 'Image size exceeds 5MB limit'
                    })
                    continue
                
                # Validate file type
                allowed_types = ['image/jpeg', 'image/png', 'image/jpg']
                if image_file.content_type not in allowed_types:
                    failed_documents.append({
                        'document_type': doc_type,
                        'reason': 'Only JPEG and PNG images are allowed'
                    })
                    continue
                
                # Check if field exists in model (for profile_photo)
                if doc_type == 'profile_photo' and not hasattr(rider, 'profile_photo'):
                    failed_documents.append({
                        'document_type': doc_type,
                        'reason': 'Profile photo upload is not supported'
                    })
                    continue
                    
                try:
                    # Set the field with the uploaded file
                    setattr(rider, field_name, image_file)
                    uploaded_documents.append(doc_type)
                except Exception as e:
                    failed_documents.append({
                        'document_type': doc_type,
                        'reason': 'Error processing file'
                    })
        
        # If we have any successful uploads, save the model
        if uploaded_documents:
            try:
                # Save only the fields that were updated plus updated_at
                update_fields = [field_mapping[doc] for doc in uploaded_documents]
                update_fields.append('updated_at')
                rider.save(update_fields=update_fields)
                
                # Check if all required documents are now uploaded
                required_fields = ['drivers_license_front', 'drivers_license_back', 
                                'vehicle_registration', 'vehicle_insurance']
                
                all_documents_uploaded = all(getattr(rider, field) for field in required_fields)
                if all_documents_uploaded and rider.status == 'inactive':
                    rider.status = 'pending_verification'
                    rider.save(update_fields=['status', 'updated_at'])
            except Exception as e:
                return internal_server_error_response(message='Error saving documents')
        
        # Return response with status of all uploads
        return Response({
            'success': len(uploaded_documents) > 0,
            'uploaded_documents': [doc.replace('_', ' ').title() for doc in uploaded_documents],
            'failed_documents': failed_documents,
            'verification_status': rider.status
        }, status=status.HTTP_200_OK if uploaded_documents else status.HTTP_400_BAD_REQUEST)






class OrderTrackingDetailView(generics.RetrieveAPIView):
    permission_classes = []  # Allow public access with order ID
    
    def get(self, request, order_id):
        try:
            order = Order.objects.select_related('rider', 'customer', 'vendor').get(id=order_id)
            
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
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c



