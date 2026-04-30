from rest_framework import serializers
from wallet.models import WalletTransaction



class AdminWalletTransactionSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'id',
            'user',
            'amount',
            'transaction_type',
            'description',
            'status',
            'external_reference',
            'reference_code',
            'order',
            'created_at',
            'updated_at',
        ]


    def get_user(self,obj:WalletTransaction):
        user = obj.user or (obj.wallet.user if obj.wallet_id and obj.wallet else None)
        if user:
            return {
                'id': user.id,
                'full_name': user.full_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                "role": user.role
            }
        return None
