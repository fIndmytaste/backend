from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from admin_manager.serializers.transactions import AdminWalletTransactionSerializer
from helpers.response.response_format import paginate_success_response_with_serializer
from product.models import Product

from wallet.models import WalletTransaction




class AdminGetTransactionsListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminWalletTransactionSerializer
    queryset = WalletTransaction.objects.all()


    def get(self, request):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.queryset,
            page_size=int(request.GET.get('page_size',20))
        )
    
