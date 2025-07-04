from rest_framework import serializers
from .models import Favorite, Order, OrderItem, Product, Rating, ProductImage



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
            "delivery_status",
            'created_at', 
            'updated_at'
        ]

    def create(self, validated_data):
        """Create the order and order items."""
        # get the user from frequest
        request = self.context.get('request')
        user = request.user if request else None

        items_data = validated_data.pop('items')
        order = Order.objects.create(user=user, **validated_data)

        # Create order items and calculate total amount
        for item_data in items_data:
            try:
                product = Product.objects.get(id=item_data['product'])
            except:
                raise serializers.ValidationError({'product': 'Product not found'})
            
            OrderItem.objects.create(order=order, product=product, quantity=item_data['quantity'], price=product.price)

        order.update_total_amount()
        return order





class FavoriteSerializer(serializers.ModelSerializer):
    product = BuyerProductSerializer()  # Serialize the product object

    class Meta:
        model = Favorite
        fields = ['user', 'product', 'created_at']
        read_only_fields = ['user', 'created_at']




class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'product', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
