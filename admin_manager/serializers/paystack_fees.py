from rest_framework import serializers

from wallet.models import PaystackFeeRecord


class PaystackFeeRecordSerializer(serializers.ModelSerializer):
    """One Paystack money movement and the fee it cost the platform."""

    user = serializers.SerializerMethodField()
    order = serializers.SerializerMethodField()
    fee_percent_of_gross = serializers.SerializerMethodField()

    class Meta:
        model = PaystackFeeRecord
        fields = [
            'id',
            'direction',
            'reference',
            'paystack_id',
            'channel',
            'currency',
            'gross_amount',
            'fee_amount',
            'net_amount',
            'fee_percent_of_gross',
            'is_estimated',
            'source',
            'paid_at',
            'user',
            'order',
            'wallet_transaction',
            'created_at',
        ]

    def get_user(self, obj: PaystackFeeRecord):
        user = obj.user
        if not user:
            return None
        return {
            'id': user.id,
            'full_name': (
                user.full_name
                or f"{user.first_name or ''} {user.last_name or ''}".strip()
                or user.email
            ),
            'email': user.email,
            'role': user.role,
        }

    def get_order(self, obj: PaystackFeeRecord):
        if not obj.order_id:
            return None
        return {
            'id': obj.order_id,
            'track_id': getattr(obj.order, 'track_id', None),
            'total_amount': getattr(obj.order, 'total_amount', None),
        }

    def get_fee_percent_of_gross(self, obj: PaystackFeeRecord):
        if not obj.gross_amount:
            return 0.0
        return round(float(obj.fee_amount) / float(obj.gross_amount) * 100, 3)
