from django.urls import path
from wallet.views import WalletBalanceView, WalletTransactionsView


urlpatterns = [ 

    path('balance', WalletBalanceView.as_view(), name='balance'),
    path('transactions', WalletTransactionsView.as_view(), name='transactions-list'),
    
]
