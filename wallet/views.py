from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from wallet.models import Wallet, WalletTransaction
from wallet.serializers import WalletSerializer, WalletTransactionSerializer

# Create your views here.




class WalletBalanceView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletSerializer

    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)




class WalletTransactionsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer

    def get_queryset(self):
        return WalletTransaction.objects.filter(user=self.request.user).order_by('-created_at')
    

