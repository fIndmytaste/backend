# serializers.py
from rest_framework import serializers

from account.models import Rider
from product.models import DeliveryTracking, Order

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        ref_name = 'RiderOrder'
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'track_id')


class RiderSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    active_orders_count = serializers.IntegerField(read_only=True)
    current_location = serializers.DictField(read_only=True)
    
    class Meta:
        model = Rider
        fields = [
            'id', 'user', 'user_name', 'mode_of_transport', 'vehicle_number',
            'status', 'is_verified', 'is_online', 'active_orders_count',
            'current_location', 'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'user', 'created_at', 'updated_at')
    
    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class DeliveryTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryTracking
        fields = '__all__'
        read_only_fields = ('id', 'order', 'created_at', 'updated_at')


class RiderLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

