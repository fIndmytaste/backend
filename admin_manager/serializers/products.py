from rest_framework import serializers
from product.models import SystemCategory



class AdminProductCategoriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemCategory
        fields = '__all__'