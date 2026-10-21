from django.contrib import admin
from .models import PaystackFeeRecord, Wallet, WalletTransaction
# Register your models here.


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    # Show whose wallet each row is, not just "Wallet for <email>".
    list_display = ('owner_name', 'owner_email', 'owner_role', 'balance', 'updated_at')
    list_select_related = ('user',)
    list_filter = ('user__role',)
    search_fields = ('user__full_name', 'user__email', 'user__phone_number')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-updated_at',)

    @admin.display(description='Name', ordering='user__full_name')
    def owner_name(self, obj):
        return obj.user.full_name or '—'

    @admin.display(description='Email', ordering='user__email')
    def owner_email(self, obj):
        return obj.user.email

    @admin.display(description='Type', ordering='user__role')
    def owner_role(self, obj):
        return {'buyer': 'Customer', 'vendor': 'Vendor', 'rider': 'Rider'}.get(
            obj.user.role, obj.user.role)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference_code', 'owner_name', 'owner_role', 'transaction_type',
        'amount', 'status', 'created_at',
    )
    list_select_related = ('user', 'wallet__user')
    list_filter = ('transaction_type', 'status', 'user__role')
    search_fields = (
        'reference_code', 'external_reference', 'description',
        'user__full_name', 'user__email', 'wallet__user__full_name', 'wallet__user__email',
    )
    readonly_fields = ('reference_code', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'

    def _owner(self, obj):
        return obj.user or (obj.wallet.user if obj.wallet_id else None)

    @admin.display(description='Name')
    def owner_name(self, obj):
        owner = self._owner(obj)
        return (owner.full_name or owner.email) if owner else '—'

    @admin.display(description='Type')
    def owner_role(self, obj):
        owner = self._owner(obj)
        if not owner:
            return '—'
        return {'buyer': 'Customer', 'vendor': 'Vendor', 'rider': 'Rider'}.get(owner.role, owner.role)


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
