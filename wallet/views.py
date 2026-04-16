from account.models import User, Vendor
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from helpers.paystack import PaystackManager
from helpers.response.response_format import internal_server_error_response, success_response, bad_request_response,paginate_success_response_with_serializer
from wallet.models import Wallet, WalletTransaction
from wallet.serializers import WalletSerializer, WalletTransactionSerializer, WithdrawalSerializer

# Create your views here.


class WalletBalanceView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletSerializer
    queryset = Wallet.objects.all()

    @swagger_auto_schema(
        operation_description="Retrieve the user's wallet balance.",
        operation_summary="Fetch the current wallet balance of the authenticated user.",
        responses={200: WalletSerializer, 401: 'Unauthorized access'}
    )
    def get(self, request, *args, **kwargs):
        """
        GET request to retrieve the current wallet balance for the authenticated user.

        **Responses:**
        - 200: Successfully retrieved wallet balance.
        - 401: Unauthorized access.
        """
        query_set = self.get_queryset()

        return success_response(
            data=self.serializer_class(query_set.first()).data,
        )

    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)


class WalletTransactionsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer
    queryset = WalletTransaction.objects.all()

    @swagger_auto_schema(
        operation_description="Retrieve a list of transactions associated with the user's wallet.",
        operation_summary="Fetch all wallet transactions for the authenticated user.",
        responses={200: WalletTransactionSerializer(many=True), 401: 'Unauthorized access'}
    )
    def get(self, request, *args, **kwargs):
        """
        GET request to retrieve the list of wallet transactions for the authenticated user.

        **Responses:**
        - 200: Successfully retrieved wallet transactions.
        - 401: Unauthorized access.
        """
        transaction_type = request.GET.get('type')

        query_set = self.get_queryset()

        if transaction_type:
            query_set = query_set.filter(transaction_type=transaction_type)

        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            query_set,
            page_size=int(request.GET.get('page_size',10))
        )

    def get_queryset(self):
        return WalletTransaction.objects.filter(wallet__user=self.request.user).order_by('-created_at')



class WalletTransactionsWebhookView(generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        klass = PaystackManager()
        return klass.handle_webhook(request)




class WithdrawalView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    serializer_class = WithdrawalSerializer
    def post(self, request):
        serializer = WithdrawalSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return bad_request_response(message=serializer.errors)

        user:User = request.user
        
        paystack_manager = PaystackManager()
        vendor_account = Vendor.objects.filter(user=user).first()
         
        
        amount = serializer.validated_data['amount']
        bank_code = None
        account_number = None

        if (not user.bank_account or not user.bank_account or user.bank_name):
            if vendor_account and (not vendor_account.bank_account or not vendor_account.bank_account or vendor_account.bank_name):
                return bad_request_response(
                    message='You have not provided your bank account details. Please update your bank account details to proceed'
                )
            
        account_number = user.bank_account or vendor_account.bank_account if vendor_account else None

        if not account_number:
            return bad_request_response(
                message='You have not provided your bank account details. Please update your bank account details to proceed'
            )


        

        # Get user's wallet
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            return bad_request_response(message="Wallet not found for this user.")

        # Check if sufficient balance
        if float(wallet.balance) < float(amount):
            return bad_request_response(message="Insufficient funds in wallet.")

        # Get vendor details
        vendor = Vendor.objects.filter(user=user).first()

        # Create a wallet transaction
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            user=user,
            amount=amount,
            transaction_type='withdrawal',
            status='pending',
            description='Withdrawal from wallet'
        )
        # Validate bank if provided in request
        if bank_code:
            is_valid, bank_result = paystack_manager.validate_bank(bank_code)
            if not is_valid:
                transaction.status = 'failed'
                transaction.save()
                return bad_request_response(message=bank_result)

        # Process withdrawal
        return paystack_manager.make_withdrawal(request, vendor, amount, transaction)
