from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema

from wallet.models import Wallet, WalletTransaction
from wallet.serializers import WalletSerializer, WalletTransactionSerializer

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
        return super().get(request, *args, **kwargs)

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
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return WalletTransaction.objects.filter(user=self.request.user).order_by('-created_at')


