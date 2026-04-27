from rest_framework import serializers
from vendor.serializers import VendorSerializer
from .models import DeliveryZone, ProductVariantCategory, UserFavoriteVendor, Order, OrderItem, Product, Rating, ProductImage, UserFavoriteVendor



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
    total_commission = serializers.SerializerMethodField()
    whole_price = serializers.SerializerMethodField()
    promo_discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payment_status = serializers.ChoiceField(choices=Order.PAYMENT_STATUS_CHOICES)
    delivery_zone = serializers.SerializerMethodField()
    
    def get_total_commission(self, obj):
        """Get the total commission for the order."""
        return float(obj.calculate_total_commission())
    
    def get_whole_price(self, obj):
        """Get the final payable price shown to the customer.
        total_amount already includes commission (stored as price_with_commission at purchase).
        service_fee is not added here — commission IS the service fee baked into product prices.
        """
        from decimal import Decimal
        total_amount = float(obj.total_amount or Decimal('0.00'))
        delivery_fee = float(obj.delivery_fee or Decimal('0.00'))
        promo_discount_amount = float(obj.promo_discount_amount or Decimal('0.00'))
        return float(max(0.0, total_amount + delivery_fee - promo_discount_amount))

    def get_delivery_zone(self, obj):
        latitude = obj.delivery_latitude or obj.location_latitude
        longitude = obj.delivery_longitude or obj.location_longitude
        if latitude is None or longitude is None:
            return None

        try:
            zone = DeliveryZone.get_zone_for_location(float(latitude), float(longitude))
        except (TypeError, ValueError):
            return None

        if not zone:
            return None

        return {
            "id": str(zone.id),
            "name": zone.name,
            "fixed_fee": float(zone.fixed_fee),
        }

    class Meta:
        model = Order
        fields = [
            'id', 
            'user', 
            'status', 
            'total_amount',
            'total_commission',
            'whole_price', 
            'promo_discount_amount',
            'payment_status', 
            'payment_method',
            'items',  
            'note',
            "address",
            "actual_delivery_time",
            "actual_pickup_time",
            "track_id",
            "delivery_fee",
            "delivery_otp",
            "location_latitude",
            "location_longitude",
            "delivery_status",
            "delivery_zone",
            "delivered_at",
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


    def _compute_rider_display_earning(self, instance):
        if instance.rider and instance.rider.is_in_house_rider:
            return 0.0
        return float(instance.calculate_net_rider_earning())

    def to_representation(self, instance: Order):
        rep = super().to_representation(instance)
        context = self.context or {}

        # Use prefetched relations — no extra DB hits when queryset has prefetch_related
        items_list = []
        items = list(instance.items.all())
        for item in items:
            product = item.product
            product_images = list(product.productimage_set.all())
            variant_selections = list(item.variant_selections.all())

            if product.parent:
                parent = product.parent
                parent_images = list(parent.productimage_set.all())
                variant_categories = list(product.productvariantcategory_set.all())
                items_list.append({
                    'product': {
                        'id': parent.id,
                        'name': parent.name,
                        'price': float(parent.price),
                        'images': ProductImageSerializerClass(parent_images, many=True).data,
                    },
                    'price': float(item.price),
                    'unit_price': float(item.price),
                    'quantity': item.quantity,
                    'variants': [{
                        'id': product.id,
                        'variant_category_name': (
                            variant_categories[0].category_name if variant_categories else None
                        ),
                        'name': product.name,
                        'price': float(item.price),
                        'quantity': item.quantity,
                        'images': ProductImageSerializerClass(product_images, many=True).data,
                    }],
                })
            else:
                variants_data = []
                for variant_selection in variant_selections:
                    variant_obj = variant_selection.variant
                    variants_data.append({
                        'id': str(variant_obj.id),
                        'variant_category_name': getattr(variant_obj.category, 'category_name', None),
                        'name': variant_obj.name,
                        'price': float(variant_selection.price_at_purchase),
                        'quantity': variant_selection.quantity,
                    })
                items_list.append({
                    'product': {
                        'id': product.id,
                        'name': product.name,
                        'price': float(product.price),
                        'images': ProductImageSerializerClass(product_images, many=True).data,
                    },
                    'price': float(item.price),
                    'unit_price': float(item.price),
                    'quantity': item.quantity,
                    'variants': variants_data,
                })

        rep['items'] = items_list

        if context.get('include_delivery_info'):
            rep['user'] = {
                'id': instance.user.id,
                'full_name': instance.user.full_name,
                'first_name': instance.user.first_name,
                'last_name': instance.user.last_name,
                'email': instance.user.email,
                'phone_number': instance.user.phone_number,
            } if instance.user else None

            rep['rider'] = {
                'id': instance.rider.id,
                'full_name': instance.rider.user.full_name,
                'first_name': instance.rider.user.first_name,
                'last_name': instance.rider.user.last_name,
                'email': instance.rider.user.email,
                'phone_number': instance.rider.user.phone_number,
            } if instance.rider else None

            rep['vendor'] = {
                'id': instance.vendor.id,
                'name': instance.vendor.name,
                'email': instance.vendor.email,
                'full_name': instance.vendor.user.full_name,
                'first_name': instance.vendor.user.first_name,
                'last_name': instance.vendor.user.last_name,
                'location_latitude': instance.vendor.location_latitude,
                'location_longitude': instance.vendor.location_longitude,
                'address': instance.vendor.address,
                'phone_number': instance.vendor.phone_number,
            } if instance.vendor else None

        rep['items_total'] = float(instance.total_amount or 0)
        rep['service_fee'] = 0
        rep['promo_discount_amount'] = float(instance.promo_discount_amount or 0)
        rep['delivery_fee'] = float(instance.delivery_fee or 0)
        rep['total_amount'] = self.get_whole_price(instance)
        rep['rider_display_earning'] = self._compute_rider_display_earning(instance)

        from django.utils import timezone as tz
        now = tz.now()
        estimated_pickup_time = None
        estimated_dropoff_time = None
        if instance.actual_pickup_time:
            estimated_pickup_time = instance.actual_pickup_time.isoformat()
        elif instance.new_estimated_delivery_time:
            half_duration = instance.new_estimated_delivery_time / 2
            estimated_pickup_time = (now + half_duration).isoformat()
        if instance.actual_delivery_time:
            estimated_dropoff_time = instance.actual_delivery_time.isoformat()
        elif instance.new_estimated_delivery_time:
            estimated_dropoff_time = (now + instance.new_estimated_delivery_time).isoformat()
        rep['estimated_pickup_time'] = estimated_pickup_time
        rep['estimated_dropoff_time'] = estimated_dropoff_time

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


class PromoCodeSerializer(serializers.ModelSerializer):
    """
    Serializer for PromoCode model.
    Returns promo code details without sensitive information.
    """
    promo_type_display = serializers.CharField(source='get_promo_type_display', read_only=True)
    is_valid = serializers.SerializerMethodField()
    validation_message = serializers.SerializerMethodField()
    
    class Meta:
        from product.promo_models import PromoCode
        model = PromoCode
        fields = [
            'id',
            'code',
            'promo_type',
            'promo_type_display',
            'value',
            'min_order_value',
            'max_discount',
            'max_distance_km',
            'start_date',
            'end_date',
            'is_active',
            'is_automatic',
            'is_valid',
            'validation_message',
        ]
        read_only_fields = ['id', 'code', 'is_active', 'is_automatic']
    
    def get_is_valid(self, obj):
        """Check if the promo code is currently valid based on context."""
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        
        # Get optional validation context from the request
        order_value = float(request.query_params.get('order_value', 0)) if request else 0
        distance = float(request.query_params.get('distance', 0)) if request else None
        vendor_id = request.query_params.get('vendor_id') if request else None
        
        vendor = None
        if vendor_id:
            from account.models import Vendor
            vendor = Vendor.objects.filter(id=vendor_id).first()
        
        is_valid, message = obj.is_valid_for_calculation(
            user=user,
            order_value=order_value,
            distance=distance,
            vendor=vendor
        )
        return is_valid
    
    def get_validation_message(self, obj):
        """Get validation message for the promo code."""
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        
        # Get optional validation context from the request
        order_value = float(request.query_params.get('order_value', 0)) if request else 0
        distance = float(request.query_params.get('distance', 0)) if request else None
        vendor_id = request.query_params.get('vendor_id') if request else None
        
        vendor = None
        if vendor_id:
            from account.models import Vendor
            vendor = Vendor.objects.filter(id=vendor_id).first()
        
        is_valid, message = obj.is_valid_for_calculation(
            user=user,
            order_value=order_value,
            distance=distance,
            vendor=vendor
        )
        return message
