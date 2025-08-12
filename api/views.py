import uuid
from django.shortcuts import render
from helpers.services.firebase_service import FirebaseNotificationService
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema 
from drf_yasg import openapi 
from account.serializers import BankAccountValidationSerializer, UserSerializer
from helpers.paystack import PaystackManager
from helpers.response.response_format import success_response, paginate_success_response_with_serializer, bad_request_response, internal_server_error_response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from product.models import DeliveryTracking, Order
from rider.serializers import OrderSerializer



class TestingWebsocketView(generics.GenericAPIView):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_layer = get_channel_layer()

    def get(self, request):
        room_group_name = 'testing_socket_connection'

        async_to_sync(self.channel_layer.group_send)(
            room_group_name,
            {
                'type': 'rider_location_update',
                'data': {
                    'order_id': str(uuid.uuid4()),
                    'rider_location': {},
                }
            }
        )

        return success_response()



class TestPushNotificationView(generics.GenericAPIView):
    """
    API endpoint to send test push notification to an FCM token.
    """

    def post(self, request, *args, **kwargs):
        token = request.data.get('token')
        if not token:
            return bad_request_response(message="FCM token is required")
        
        try:
            result = FirebaseNotificationService.send_notification_to_token(
                token=token,
                title="Test Notification",
                body="This is a test push notification!"
            )
            return success_response(data={"success": True, "result": result})
        
        except Exception as e:
            return internal_server_error_response(message=str(e))

class GetAllBanksView(generics.GenericAPIView):

    @swagger_auto_schema(
        operation_description="Retrieve a list of all banks",
        operation_summary="Get all banks",
    )
    def get(self,request):
        klass = PaystackManager()
        success, response = klass.banks( )
        return success_response(data=response) if success else bad_request_response(message=response)
    


class ValidateBankAccountNumber(generics.GenericAPIView):
    permission_classes = []
    serializer_class = BankAccountValidationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data) 
        serializer.is_valid(raise_exception=True)

        klass = PaystackManager()
        
        success, response = klass.resolve_bank_account(
            request.data['account_number'],
            request.data['bank_code'],
        )
        return success_response(data=response) if success else bad_request_response(message=response)



class CustomerOrdersListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    queryset = Order.objects.all().order_by('-created_at')

    def get(self,request):
        """
        Retrieve a list of all orders for the authenticated user.
        """
        status = request.GET.get('status')
        queryset = self.get_queryset().filter(user=request.user)
        if status:
            queryset = queryset.filter(status=status)
            
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            queryset,
            page_size=int(request.GET.get('page_size',20))
        )
