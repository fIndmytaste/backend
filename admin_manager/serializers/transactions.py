from rest_framework import serializers
from account.models import Vendor
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


    def get_user(self, obj: WalletTransaction):
        user = obj.user or (obj.wallet.user if obj.wallet_id and obj.wallet else None)
        if not user:
            return None

        # Payout destination, so an admin reviewing a withdrawal can see where
        # the money is actually going without leaving the transactions tab.
        # Mirrors the wallet's own resolution order: a vendor's own copy when
        # it is filled in, otherwise the user record, which is where a rider's
        # details live.
        bank_account = user.bank_account
        bank_name = user.bank_name
        bank_account_name = user.bank_account_name
        if not (bank_account and bank_name):
            # Only reached for rows saved before bank details were mirrored
            # onto the user, so this stays off the hot path of a listing.
            vendor = Vendor.objects.filter(user=user).first()
            if vendor:
                bank_account = bank_account or vendor.bank_account
                bank_name = bank_name or vendor.bank_name
                bank_account_name = bank_account_name or vendor.bank_account_name

        return {
            'id': user.id,
            'full_name': user.full_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            'email': user.email,
            "role": user.role,
            'bank_account': bank_account or None,
            'bank_name': bank_name or None,
            'bank_account_name': bank_account_name or None,
        }
