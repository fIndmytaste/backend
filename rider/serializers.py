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

    def _get_whole_price(self, instance: Order) -> float:
        """items_total + delivery_fee - promo_discount.
        Commission is baked into item prices — service_fee is not added separately.
        """
        from decimal import Decimal
        items_total = float(instance.total_amount or Decimal('0.00'))
        delivery_fee = float(instance.delivery_fee or Decimal('0.00'))
        promo_discount = float(instance.promo_discount_amount or Decimal('0.00'))
        return max(0.0, items_total + delivery_fee - promo_discount)

    def _compute_rider_display_earning(self, instance: Order) -> float:
        return float(instance.calculate_net_rider_earning())

    def to_representation(self, instance: Order):
        addition_serializer_data = self.context.get('addition_serializer_data')

        # Call super to get default representation
        representation = super().to_representation(instance)

        if instance.vendor:
            representation['vendor'] = dict(
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
            representation['vendor'] = None

        if addition_serializer_data:
            if isinstance(addition_serializer_data,dict) and addition_serializer_data.get('rider_order_details'):
                vendor:Vendor = instance.vendor
                pick_up_details = {
                    'address': vendor.address if vendor else '',
                    'time':instance.actual_pickup_time
                }
                representation['pick_up_details'] = pick_up_details
                representation['distance'] = 10.05
                representation['earning'] = 4000

                order_items = (
                    OrderItem.objects
                    .filter(order=instance)
                    .select_related('product')
                    .prefetch_related('product__productimage_set')
                )
                items = [dict(
                    id=item.id,
                    product_name=item.product.name,
                    product_images=item.product.all_images(),
                    quantity=item.quantity,
                    price=item.price,
                ) for item in order_items]
                representation['items'] = items

        # Overwrite total_amount with the customer-facing grand total
        # (items + delivery - discount). Commission is already inside item prices.
        representation['total_amount'] = self._get_whole_price(instance)
        representation['items_total'] = float(instance.total_amount or 0)
        representation['service_fee'] = 0
        representation['delivery_fee'] = float(instance.delivery_fee or 0)
        representation['discount_amount'] = float(instance.promo_discount_amount or 0)

        # rider_display_earning = delivery fee after platform commission is deducted.
        # PlatformSettings is fetched once per serializer instance, not per order.
        representation['rider_display_earning'] = self._compute_rider_display_earning(instance)

        return representation


def _compute_rider_earning(instance: Order) -> float:
    """Net delivery earning after platform commission is deducted."""
    return float(instance.calculate_net_rider_earning())


class RiderOrderDetailSerializer(serializers.Serializer):
    """
    Lean, read-only serializer for the rider order detail screen.
    Returns exactly the fields the screen uses — nothing else.
    """

    def to_representation(self, instance: Order):
        from django.utils import timezone as tz
        now = tz.now()

        # --- items: only what OrderItemsWidget renders ---
        items = []
        for item in instance.items.all():
            product = item.product
            images = list(product.productimage_set.all())
            # only the first image is ever shown
            first_image = images[0].image_url if images else None

            # variant line totals (used for total price computation on Flutter side)
            variants = []
            for vs in item.variant_selections.all():
                variants.append({
                    'price': float(vs.price_at_purchase),
                    'quantity': vs.quantity,
                })

            items.append({
                'product': {
                    'id': str(product.id),
                    'name': product.name,
                    'price': float(product.price),
                    'images': [{'image': first_image}] if first_image else [],
                },
                'quantity': item.quantity,
                'price': float(item.price),
                'variants': variants,
            })

        # --- vendor: address, name, phone, coordinates for navigation ---
        vendor = instance.vendor
        vendor_data = None
        if vendor:
            vendor_data = {
                'id': str(vendor.id),
                'name': vendor.name,
                'full_name': vendor.user.full_name if vendor.user else '',
                'phone_number': vendor.phone_number,
                'address': vendor.address,
                'location_latitude': str(vendor.location_latitude or ''),
                'location_longitude': str(vendor.location_longitude or ''),
            }

        # --- customer: name + phone for contact card ---
        customer = instance.user
        customer_data = None
        if customer:
            customer_data = {
                'id': str(customer.id),
                'full_name': customer.full_name,
                'phone_number': customer.phone_number,
            }

        # --- estimated times ---
        estimated_pickup_time = None
        estimated_dropoff_time = None
        if instance.actual_pickup_time:
            estimated_pickup_time = instance.actual_pickup_time.isoformat()
        elif instance.new_estimated_delivery_time:
            estimated_pickup_time = (now + instance.new_estimated_delivery_time / 2).isoformat()
        if instance.actual_delivery_time:
            estimated_dropoff_time = instance.actual_delivery_time.isoformat()
        elif instance.new_estimated_delivery_time:
            estimated_dropoff_time = (now + instance.new_estimated_delivery_time).isoformat()

        return {
            'id': str(instance.id),
            'track_id': instance.track_id or '',
            'status': instance.status,
            'delivery_status': instance.delivery_status or '',
            'address': instance.address or '',
            'location_latitude': str(instance.location_latitude or ''),
            'location_longitude': str(instance.location_longitude or ''),
            'note': instance.note or '',
            'rider_display_earning': _compute_rider_earning(instance),
            'delivery_fee': float(instance.delivery_fee or 0),
            'total_distance': float(instance.total_distance or 0),
            'estimated_pickup_time': estimated_pickup_time,
            'estimated_dropoff_time': estimated_dropoff_time,
            'actual_pickup_time': instance.actual_pickup_time.isoformat() if instance.actual_pickup_time else None,
            'actual_delivery_time': instance.actual_delivery_time.isoformat() if instance.actual_delivery_time else None,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'items': items,
            'vendor': vendor_data,
            'user': customer_data,
        }


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
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)



from .guarantor_serializer import GuarantorSerializer

class RiderDocumentUploadSerializer(serializers.Serializer):
    """
    Serializer for handling rider document uploads and extra info.
    """
    license_front = serializers.ImageField(required=False)
    license_back = serializers.ImageField(required=False)
    vehicle_registration = serializers.ImageField(required=False)
    vehicle_insurance = serializers.ImageField(required=False)
    profile_photo = serializers.ImageField(required=False)

    vehicle_brand = serializers.CharField(required=False, allow_blank=True)
    plate_number = serializers.CharField(required=False, allow_blank=True)
    next_of_kin = serializers.CharField(required=False, allow_blank=True)
    next_of_kin_phone = serializers.CharField(required=False, allow_blank=True)
    preferred_location = serializers.CharField(required=False, allow_blank=True)

    # guarantors = GuarantorSerializer(many=True, required=True)

    # def validate_guarantors(self, value):
    #     if not isinstance(value, list) or len(value) < 2:
    #         raise serializers.ValidationError("At least 2 guarantors are required.")
    #     return value


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
    

class RiderLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)


class DeliveryTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryTracking
        fields = '__all__'