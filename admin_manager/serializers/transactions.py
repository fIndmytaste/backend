from rest_framework import serializers
from wallet.models import WalletTransaction



class AdminWalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = '__all__'