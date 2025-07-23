# serializers.py
from rest_framework import serializers

from account.models import Rider, RiderRating, Vendor
from account.serializers import UserSerializer
from product.models import DeliveryTracking, Order, OrderItem

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        ref_name = 'RiderOrder'
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'track_id')


    def to_representation(self, instance:Order):
        addition_serializer_data = self.context.get('addition_serializer_data')
        
        # Call super to get default representation
        representation = super().to_representation(instance)

        if addition_serializer_data:
            if isinstance(addition_serializer_data,dict) and addition_serializer_data.get('rider_order_details'):
                vendor:Vendor = instance.vendor
                pick_up_details = {
                    'address': vendor.address,
                    'time':instance.actual_pickup_time
                }
                representation['pick_up_details'] = pick_up_details
                representation['distance'] = 10.05
                representation['earning'] = 4000

                items = [dict(
                    id=item.id,
                    product_name=item.product.name,
                    product_images = item.product.all_images(),
                    quantity=item.quantity,
                    price=item.price,
                    
                ) for item in OrderItem.objects.filter(order=instance)]
                representation['items'] = items

        return representation


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
        return obj.user.get_full_name() or obj.user.email


class DeliveryTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryTracking
        fields = '__all__'
        read_only_fields = ('id', 'order', 'created_at', 'updated_at')


class RiderLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)


class RiderDocumentUploadSerializer(serializers.Serializer):
    """
    Serializer for handling rider document uploads.
    """
    license_front = serializers.ImageField(required=False)
    license_back = serializers.ImageField(required=False)
    vehicle_registration = serializers.ImageField(required=False)
    vehicle_insurance = serializers.ImageField(required=False)
    profile_photo = serializers.ImageField(required=False)


class AcceptOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()



class RiderRatingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating vendor ratings"""

    
    
    class Meta:
        model = RiderRating
        fields = ['rider','user', 'rating', 'comment','created_at']  
    
    def validate_rating(self, value):
        """Validate that rating is between 0 and 5"""
        if value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be between 0 and 5")
        return value
    
    def create(self, validated_data):
        """Create or update rating for a vendor by a user"""
        user = self.context['request'].user
        rider = validated_data['rider']
        
        # Try to get existing rating, if exists update it, otherwise create new
        rating, created = RiderRating.objects.update_or_create(
            rider=rider,
            user=user,
            defaults={
                'rating': validated_data['rating'],
                'comment': validated_data.get('comment', '')
            }
        )
        
        # Update vendor's overall rating
        self.update_vendor_rating(rider)
        
        return rating
    
    def update_vendor_rating(self, vendor):
        """Update the vendor's overall rating based on all ratings"""
        avg_rating = vendor.ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
        if avg_rating:
            vendor.rating = round(float(avg_rating), 2)
            vendor.save(update_fields=['rating'])


    def to_representation(self, instance:RiderRating):
        """Return a custom representation of the rating"""
        response = super().to_representation(instance)
        if instance.user:
            response['user'] = UserSerializer(instance.user).data
        return response