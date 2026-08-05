from django.contrib import admin
from .models import PaystackFeeRecord, Wallet, WalletTransaction
# Register your models here.


admin.site.register(WalletTransaction)
admin.site.register(Wallet)


@admin.register(PaystackFeeRecord)
class PaystackFeeRecordAdmin(admin.ModelAdmin):
    list_display = (
        'paid_at', 'direction', 'channel', 'gross_amount',
        'fee_amount', 'net_amount', 'is_estimated', 'reference',
    )
    list_filter = ('direction', 'is_estimated', 'source', 'channel')
    search_fields = ('reference', 'paystack_id', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'raw_payload')
    date_hierarchy = 'paid_at'
