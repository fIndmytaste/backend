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
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_primary', 'is_active']

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


class ProductSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)  # Add images to the serialized product

    class Meta:
        model = Product
        fields = [
            'id','name','description','price',
            'system_category','category','stock','is_active',
            'is_delete','is_featured','views','discounted_price','images']

    def to_representation(self, instance: Product):
        images = ProductImage.objects.filter(product=instance)
        data = super().to_representation(instance)
        data['images'] = ProductImageSerializer(images, many=True, context=self.context).data
        return data

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()

    
    
    def create(self, validated_data):
        user = self.context['request'].user  # Get the current user from the request
        vendor = Vendor.objects.get(user=user)  # Assuming Vendor is a model related to User

        # Add the vendor to the validated data
        validated_data['vendor'] = vendor

        return super().create(validated_data)



class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = '__all__'


class VendorSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    class Meta:
        model = Vendor
        fields = '__all__'


    def get_thumbnail(self, obj):
        request = self.context.get('request')
        return obj.thumbnail.url if obj.thumbnail else None
    

    def get_logo(self, obj):
        request = self.context.get('request')
        return obj.logo.url if obj.logo else None





class VendorRegisterBusinessSerializer(serializers.Serializer):
    category = serializers.UUIDField(required=True)
    name = serializers.CharField(required=True)
    description = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    open_day = serializers.CharField(required=True)
    close_day = serializers.CharField(required=True)
    open_time = serializers.TimeField(required=True)
    close_time = serializers.TimeField(required=True)