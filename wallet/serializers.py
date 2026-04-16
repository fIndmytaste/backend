import uuid
from account.models import Vendor
from rest_framework import serializers
from .models import Wallet, WalletTransaction
from decimal import Decimal
class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['user', 'balance']

    def to_representation(self, instance:Wallet):
        data = super().to_representation(instance)
        data['bank_details'] = dict(
            id=instance.user.id,
            bank_account=instance.user.bank_account,
            bank_name=instance.user.bank_name,
            bank_account_name=instance.user.bank_account_name,
        )
        return data


class WalletTransactionSerializer(serializers.ModelSerializer):
    reference_code = serializers.SerializerMethodField()
    class Meta:
        model = WalletTransaction
        fields = ['id', 'wallet', 'amount', 'transaction_type','reference_code','description', 'status', 'created_at']



    def get_reference_code(self, obj:WalletTransaction):
        if obj.reference_code:
            return obj.reference_code

        prefixes = WalletTransaction.TRANSACTION_PREFIXES
        prefix = prefixes.get(obj.transaction_type, 'TXN')
        uid = str(obj.id or uuid.uuid4()).replace('-', '')[:20].upper()
        ref_code = f"{prefix}-{uid}"

        if obj.id:
            obj.reference_code = ref_code
            obj.save(update_fields=['reference_code'])

        return ref_code
    




class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
