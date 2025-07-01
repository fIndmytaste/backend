import uuid
from rest_framework import serializers
from .models import Wallet, WalletTransaction

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['user', 'balance']


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