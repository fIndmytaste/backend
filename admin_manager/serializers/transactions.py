from rest_framework import serializers
from wallet.models import WalletTransaction



class AdminWalletTransactionSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    class Meta:
        model = WalletTransaction
        fields = '__all__'


    def get_user(self,obj:WalletTransaction):
        if obj.wallet:
            return {
                'id':obj.wallet.user.id,
                'full_name':obj.wallet.user.full_name,
            }
        else:
            return None