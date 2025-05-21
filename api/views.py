from django.shortcuts import render
from rest_framework import generics
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi  # Import for custom parameter and response types
from account.serializers import BankAccountValidationSerializer, UserSerializer
from helpers.paystack import PaystackManager
from helpers.response.response_format import bad_request_response, success_response
# Create your views here.


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

        success_ , bank_name = klass.validate_bank(request.data['bank_code'])
        return success_response(message=bank_name,data=response) if success else bad_request_response(message=response)