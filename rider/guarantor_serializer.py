from rest_framework import serializers
from account.models import Guarantor

class GuarantorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guarantor
        fields = ['id', 'name', 'phone_number', 'relationship']
        read_only_fields = ['id']
