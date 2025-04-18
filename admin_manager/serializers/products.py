from rest_framework import serializers
from product.models import Favorite, Order, OrderItem, Product, Rating, SystemCategory



class AdminProductCategoriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemCategory
        fields = '__all__'