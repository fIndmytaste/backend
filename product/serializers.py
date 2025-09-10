from rest_framework import serializers
from vendor.serializers import VendorSerializer
from .models import UserFavoriteVendor, Order, OrderItem, Product, Rating, ProductImage, UserFavoriteVendor



class ProductImageSerializerClass(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    class Meta:
        model = ProductImage
        fields = ['id', 'image','is_primary','is_active']

    def get_image(self,obj:ProductImage):
        return obj.get_image_url()
    
class BuyerProductSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    class Meta:
        model = Product
        fields = '__all__'

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()
    
    def get_images(self,obj):
        return ProductImageSerializerClass(obj.productimage_set.all(),many=True).data
        

class OrderItemSerializer(serializers.ModelSerializer):
    product = BuyerProductSerializer()

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price', 'total_price']


class OrderItemSerializerIn(serializers.Serializer):
    product = serializers.CharField()
    quantity = serializers.IntegerField(required=False)

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payment_status = serializers.ChoiceField(choices=Order.PAYMENT_STATUS_CHOICES)

    class Meta:
        model = Order
        fields = [
            'id', 
            'user', 
            'status', 
            'total_amount', 
            'payment_status', 
            'items',  
            "address",
            "actual_delivery_time",
            "actual_pickup_time",
            "track_id",
            "delivery_fee",
            "delivery_otp",
            "location_latitude",
            "location_longitude",
            "delivery_status",
            'created_at', 
            'updated_at'
        ]

    def validate(self, data):
        """Ensure the order contains at least one item."""
        items = data.get('items')
        if not items or len(items) == 0:
            raise serializers.ValidationError({"items": "Order must contain at least one item."})
        return data

    def create(self, validated_data):
        """Create the order and its items after validation."""
        request = self.context.get('request')
        user = request.user if request else None

        items_data = validated_data.pop('items')

        # Extra safety check (optional; already handled by validate())
        if not items_data:
            raise serializers.ValidationError({"items": "Cannot create order without items."})

        order = Order.objects.create(user=user, **validated_data)


        for item_data in items_data:
            try:
                product = Product.objects.get(id=item_data['product'])
            except Product.DoesNotExist:
                raise serializers.ValidationError({'product': f"Product with ID {item_data['product']} not found"})

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item_data['quantity'],
                price=product.price
            )

        order.update_total_amount()
        return order


    def to_representation(self, instance:Order):
        rep = super().to_representation(instance)
        
        context = self.context

        if context.get('include_delivery_info'):
            if instance.user:
                rep['user'] = dict(
                    id=instance.user.id,
                    full_name=instance.user.full_name,
                    first_name=instance.user.first_name,
                    last_name=instance.user.last_name,
                    email=instance.user.email,
                    email=instance.user.phone_number,
                )
            else:
                rep['user'] = None

            if instance.rider:
                rep['rider'] = dict(
                    id=instance.rider.id,
                    full_name=instance.rider.user.full_name,
                    first_name=instance.rider.user.first_name,
                    last_name=instance.rider.user.last_name,
                    email=instance.rider.user.email,
                )
            else:
                rep['rider'] = None

            if instance.vendor:
                rep['vendor'] = dict(
                    id=instance.vendor.id,
                    name=instance.vendor.name,
                    email=instance.vendor.email,
                    full_name=instance.vendor.user.full_name,
                    first_name=instance.vendor.user.first_name,
                    last_name=instance.vendor.user.last_name,
                    location_latitude=instance.vendor.location_latitude,
                    location_longitude=instance.vendor.location_longitude,
                    address=instance.vendor.address,
                )
            else:
                rep['vendor'] = None


        if context.get('addition_serializer_data',{}).get('is_vendor'):
            if instance.rider:
                rep['vendor'] = dict(
                    id=instance.vendor.id,
                    name=instance.vendor.name,
                    email=instance.vendor.email,
                    first_name=instance.vendor.user.first_name,
                    last_name=instance.vendor.user.last_name,
                )
            else:
                rep['vendor'] = None
        
        return rep
    
class CreateOrderSerializer(serializers.Serializer): 
    items = OrderItemSerializerIn(many=True,required=True)
    vendor_id = serializers.CharField(required=True)
    note = serializers.CharField(required=False)








class FavoriteSerializer(serializers.ModelSerializer):
    # vendor = BuyerProductSerializer()  # Serialize the product object

    class Meta:
        model = UserFavoriteVendor
        fields = ['user', 'vendor', 'created_at']
        read_only_fields = ['user', 'created_at']

class FavoriteVendorSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserFavoriteVendor
        fields = ['user', 'vendor', 'created_at']
        read_only_fields = ['user', 'created_at']


    def to_representation(self, instance):
        request = self.context.get('request')
        return VendorSerializer(instance.vendor, context={'request': request}).data




class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'product', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
