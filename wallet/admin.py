from django.contrib import admin
from .models import Wallet, WalletTransaction
# Register your models here.


admin.site.register(WalletTransaction)
admin.site.register(Wallet)
