import uuid
from account.models import Vendor
from rest_framework import serializers
from .models import Wallet, WalletTransaction
from decimal import Decimal
from helpers.models import DeliveryConfiguration, ConfigurationManager


DEFAULT_VENDOR_MINIMUM_WITHDRAWAL = Decimal('30000.00')
DEFAULT_RIDER_MINIMUM_WITHDRAWAL = Decimal('10000.00')


def ensure_withdrawal_config_exists(key: str, default_amount: Decimal, description: str):
    DeliveryConfiguration.objects.get_or_create(
        key=key,
        defaults={
            'category': 'thresholds',
            'data_type': 'int',
            'value': str(int(default_amount)),
            'default_value': str(int(default_amount)),
            'description': description,
            'min_value': 0,
            'max_value': 10000000,
            'is_active': True,
        },
    )


def get_minimum_withdrawal_for_user(user):
    is_vendor = Vendor.objects.filter(user=user).exists()
    key = 'vendor_minimum_withdrawal' if is_vendor else 'rider_minimum_withdrawal'
    default_amount = (
        DEFAULT_VENDOR_MINIMUM_WITHDRAWAL if is_vendor else DEFAULT_RIDER_MINIMUM_WITHDRAWAL
    )
    ensure_withdrawal_config_exists(
        key,
        default_amount,
        'Minimum wallet withdrawal amount in NGN',
    )
    configured_value = ConfigurationManager.get_config(key, int(default_amount))
    return Decimal(str(configured_value)).quantize(Decimal('0.01'))


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['user', 'balance']

    def to_representation(self, instance:Wallet):
        data = super().to_representation(instance)
        vendor = Vendor.objects.filter(user=instance.user).first()
        bank_account = vendor.bank_account if vendor and vendor.bank_account else instance.user.bank_account
        bank_name = vendor.bank_name if vendor and vendor.bank_name else instance.user.bank_name
        bank_account_name = (
            vendor.bank_account_name
            if vendor and vendor.bank_account_name
            else instance.user.bank_account_name
        )
        data['bank_details'] = dict(
            id=instance.user.id,
            bank_account=bank_account,
            bank_name=bank_name,
            bank_account_name=bank_account_name,
        )
        data['minimum_withdrawal_amount'] = str(get_minimum_withdrawal_for_user(instance.user))
        return data


class WalletTransactionSerializer(serializers.ModelSerializer):
    reference_code = serializers.SerializerMethodField()
    order_track_id = serializers.SerializerMethodField()
    class Meta:
        model = WalletTransaction
        fields = ['id', 'wallet', 'amount', 'transaction_type','reference_code','description', 'status', 'created_at', 'order_track_id']



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

    def get_order_track_id(self, obj: WalletTransaction):
        if obj.order and obj.order.track_id:
            return str(obj.order.track_id)
        return None
    




class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            minimum_amount = get_minimum_withdrawal_for_user(request.user)
            if attrs['amount'] < minimum_amount:
                raise serializers.ValidationError({
                    'amount': f'Minimum withdrawal amount is NGN {minimum_amount}'
                })
        return attrs
