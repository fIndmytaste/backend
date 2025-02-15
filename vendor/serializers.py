from rest_framework import serializers

from account.models import Vendor
from product.models import Favorite, Product, ProductImage, SystemCategory, VendorCategory

class SystemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemCategory
        fields = '__all__'


class VendorCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorCategory
        fields = '__all__'


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_primary', 'is_active']


class ProductSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)  # Add images to the serialized product

    class Meta:
        model = Product
        fields = '__all__'

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()



class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = '__all__'


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'





class VendorRegisterBusinessSerializer(serializers.Serializer):
    category = serializers.UUIDField(required=True)
    name = serializers.CharField(required=True)
    description = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    open_time = serializers.TimeField(required=True)
    close_time = serializers.TimeField(required=True)