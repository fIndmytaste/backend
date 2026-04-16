from rest_framework import serializers
from vendor.serializers import VendorSerializer
from .models import ProductVariantCategory, UserFavoriteVendor, Order, OrderItem, Product, Rating, ProductImage, UserFavoriteVendor



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
    payment_status = serializers.ChoiceField(choices=Order.PAYMENT_STATUS_CHOICES)
    
    def get_total_commission(self, obj):
        """Get the total commission for the order."""
        return float(obj.calculate_total_commission())
    
    def get_whole_price(self, obj):
        """Get the complete price: total_amount + total_commission + delivery_fee."""
        from decimal import Decimal
        total_amount = float(obj.total_amount or Decimal('0.00'))
        total_commission = float(obj.calculate_total_commission())
        delivery_fee = float(obj.delivery_fee or Decimal('0.00'))
        return float(total_amount + total_commission + delivery_fee) 

    class Meta:
        model = Order
        fields = [
            'id', 
            'user', 
            'status', 
            'total_amount',
            'total_commission',
            'whole_price', 
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


    def to_representation(self, instance: Order):
        rep = super().to_representation(instance)
        context = self.context or {}

        # Prefetch all related objects in queryset for performance
        # items, product, productimage_set, variant_categories, variant_selections, variant, variant__category
        grouped_items = {}
        # Use the prefetched items (should be prefetched in queryset)
        items = list(getattr(instance, 'items').all() if hasattr(instance, 'items') else [])
        # if context.get("full_items"):
        for item in items:
            product = item.product
            # Prefetch images and variant categories
            product_images = list(getattr(product, 'productimage_set', []).all()) if hasattr(product, 'productimage_set') else []
            variant_categories = list(getattr(product, 'variant_categories', []).all()) if hasattr(product, 'variant_categories') else []
            # Prefetch variant selections
            variant_selections = list(getattr(item, 'variant_selections', []).all()) if hasattr(item, 'variant_selections') else []

            if product.parent:
                parent = product.parent
                parent_id = str(parent.id)
                parent_images = list(getattr(parent, 'productimage_set', []).all()) if hasattr(parent, 'productimage_set') else []
                if parent_id not in grouped_items:
                    grouped_items[parent_id] = {
                        'product': {
                            'id': parent.id,
                            'name': parent.name,
                            'price': float(parent.price),
                            'quantity': 0,
                            'images': ProductImageSerializerClass(parent_images, many=True).data,
                        },
                        'quantity': 0,
                        'variants': []
                    }
                grouped_items[parent_id]['variants'].append({
                    'id': product.id,
                    'variant_category_name': (
                        variant_categories[0].category_name if variant_categories else None
                    ),
                    'name': product.name,
                    'price': float(product.price),
                    'quantity': item.quantity,
                    'images': ProductImageSerializerClass(product_images, many=True).data,
                })
            else:
                product_id = str(product.id)
                if product_id not in grouped_items:
                    grouped_items[product_id] = {
                        'product': {
                            'id': product.id,
                            'name': product.name,
                            'price': float(product.price),
                            'images': ProductImageSerializerClass(product_images, many=True).data,
                        },
                        'quantity': item.quantity,
                        'variants': []
                    }
                    for variant_selection in variant_selections:
                        variant_obj = variant_selection.variant
                        grouped_items[product_id]['variants'].append({
                            'id': str(variant_obj.id),
                            'variant_category_name': getattr(variant_obj.category, 'category_name', None),
                            'name': variant_obj.name,
                            'price': float(variant_selection.price_at_purchase),
                            'quantity': variant_selection.quantity,
                        })
                else:
                    grouped_items[product_id]['quantity'] += item.quantity

        rep['items'] = list(grouped_items.values())
        # else:
        #     # Default detailed items representation
        #     rep['items'] = [str(item.id) for item in items]

        # Optional: Include delivery/user/vendor info
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

        # Remove DB updates from serialization for speed
        rep['total_amount'] = float(instance.total_amount) + float(instance.calculate_total_commission()) + float(instance.delivery_fee or 0)
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
