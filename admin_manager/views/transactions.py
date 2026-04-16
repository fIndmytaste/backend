from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from admin_manager.serializers.transactions import AdminWalletTransactionSerializer
from helpers.response.response_format import paginate_success_response_with_serializer,bad_request_response,success_response
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
            self.get_queryset(),
            page_size=int(request.GET.get('page_size',20))
        )
    

class AdminGetTransactionDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminWalletTransactionSerializer
    queryset = WalletTransaction.objects.all()


    def get(self, request,transaction_id):
        try:
            transaction = WalletTransaction.objects.get(id=transaction_id)
        except:
            return bad_request_response(message="Transaction not found", status_code=404)

        return success_response(data=self.serializer_class(transaction).data)
    
