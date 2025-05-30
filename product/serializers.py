from rest_framework import serializers
from .models import Favorite, Order, OrderItem, Product, Rating



class BuyerProductSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = '__all__'

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()


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
            "track_id",
            'created_at', 
            'updated_at'
        ]

    def create(self, validated_data):
        """Create the order and order items."""
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)

        # Create order items and calculate total amount
        for item_data in items_data:
            product = item_data['product']
            OrderItem.objects.create(order=order, product=product, **item_data)

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
