import uuid
from django.shortcuts import render
from rest_framework import generics
from drf_yasg.utils import swagger_auto_schema 
from drf_yasg import openapi 
from account.serializers import BankAccountValidationSerializer, UserSerializer
from helpers.paystack import PaystackManager
from helpers.response.response_format import bad_request_response, success_response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync



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