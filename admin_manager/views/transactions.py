from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from admin_manager.serializers.transactions import AdminWalletTransactionSerializer
from helpers.response.response_format import paginate_success_response_with_serializer,bad_request_response,success_response
from product.models import Product

from wallet.models import WalletTransaction




class AdminGetTransactionsListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminWalletTransactionSerializer
    queryset = WalletTransaction.objects.select_related('user', 'wallet', 'wallet__user', 'order').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        status = self.request.GET.get('status', '').strip()
        transaction_type = self.request.GET.get('transaction_type', '').strip()

        if search:
            queryset = queryset.filter(
                Q(reference_code__icontains=search) |
                Q(external_reference__icontains=search) |
                Q(description__icontains=search) |
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(wallet__user__full_name__icontains=search) |
                Q(wallet__user__email__icontains=search)
            )
        if status:
            queryset = queryset.filter(status=status)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        return queryset.order_by('-created_at')


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
    queryset = WalletTransaction.objects.select_related('user', 'wallet', 'wallet__user', 'order').all()


    def get(self, request,transaction_id):
        try:
            transaction = self.get_queryset().get(id=transaction_id)
        except:
            return bad_request_response(message="Transaction not found", status_code=404)

        return success_response(data=self.serializer_class(transaction).data)
    
