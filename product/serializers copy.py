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
        from collections import defaultdict
        rep = super().to_representation(instance)
        context = self.context or {}

        grouped_items = {}
        
        for item in instance.items.all():
            product = item.product

            if product.parent:
                # This is a variant, group under parent
                parent = product.parent
                parent_id = str(parent.id)
                # variant_categories = ProductVariantCategory.objects.filter(parent_product=instance)


                if parent_id not in grouped_items:
                    grouped_items[parent_id] = {
                        'product': {
                            'id': parent.id,
                            'name': parent.name,
                            'price': float(parent.price),
                            'quantity': 0,
                            'images': ProductImageSerializerClass(parent.productimage_set.all(),many=True).data,
                            
                        },
                        'variants': []
                    }

                grouped_items[parent_id]['variants'].append({
                    'id': product.id,
                    'variant_category_name': (
                        product.variant_categories.first().category_name 
                        if product.variant_categories.exists() 
                        else None
                    ),

                    'name': product.name,
                    'price': float(product.price),  
                    'quantity': item.quantity,
                    'images' : ProductImageSerializerClass(product.productimage_set.all(),many=True).data,
                })

            else:
                if str(product.id) not in grouped_items:
                    # This is a parent product without variants (or with OrderItemVariant)
                    grouped_items[str(product.id)] = {
                        'product': {
                            'id': product.id,
                            'name': product.name,
                            'price': float(product.price),
                            'images' : ProductImageSerializerClass(product.productimage_set.all(),many=True).data,
                        },
                        'quantity': item.quantity,
                        'variants': []
                    }
                    
                    # Add OrderItemVariant selections if they exist
                    for variant_selection in item.variant_selections.all():
                        variant_obj = variant_selection.variant
                        grouped_items[str(product.id)]['variants'].append({
                            'id': str(variant_obj.id),
                            'variant_category_name': variant_obj.category.category_name,
                            'name': variant_obj.name,
                            'price': float(variant_selection.price_at_purchase),
                            'quantity': variant_selection.quantity,
                        })
                else:
                    # If already exists (should not happen), just update quantity
                    grouped_items[str(product.id)]['quantity'] += item.quantity



        # Flatten grouped structure into list
        rep['items'] = list(grouped_items.values())



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
                # add phone number
                'phone_number': instance.vendor.phone_number,
            } if instance.vendor else None

        # Calculate delivery time estimates using the helper function (always compute if data available)
        if instance.vendor and instance.location_latitude and instance.location_longitude:
            try:
                from helpers.order_utils import estimate_delivery_time, fetch_traffic_level, fetch_weather_factor, get_distance_between_two_location
                from django.utils import timezone
                # Calculate distance if not already stored
                if not instance.total_distance:
                    distance_km = get_distance_between_two_location(
                        float(instance.vendor.location_latitude),
                        float(instance.vendor.location_longitude),
                        float(instance.location_latitude),
                        float(instance.location_longitude)
                    )
                    print(f"Calculated distance_km: {distance_km}") 
                    if distance_km:
                        instance.total_distance = distance_km
                        instance.save(update_fields=['total_distance'])
                else:
                    distance_km = float(instance.total_distance)
                
                # Fetch real-time traffic and weather data
                # traffic_data = fetch_traffic_level(
                #     (float(instance.vendor.location_latitude), float(instance.vendor.location_longitude)),
                #     (float(instance.location_latitude), float(instance.location_longitude))
                # )
               
                # weather_data = fetch_weather_factor(
                #     float(instance.delivery_latitude),
                #     float(instance.delivery_longitude)
                # )
                
                # # Calculate delivery time estimation
                # time_estimate = estimate_delivery_time(distance_km, traffic_data, weather_data)
                
                # # Calculate estimated pickup and dropoff times if not already set
                # if not instance.estimated_pickup_time:
                #     pickup_minutes = time_estimate.get('preparation_time_minutes', 15)
                #     instance.estimated_pickup_time = timezone.now() + timezone.timedelta(minutes=pickup_minutes)
                
                # if not instance.estimated_dropoff_time:
                #     total_minutes = time_estimate.get('estimated_minutes', 30)
                #     instance.estimated_dropoff_time = timezone.now() + timezone.timedelta(minutes=total_minutes)
                
                # Save the updated times
                instance.save(update_fields=['estimated_pickup_time', 'estimated_dropoff_time'])
                
            except Exception as e:
                print(f"Error calculating delivery estimates: {e}")
        
            # Always include delivery time estimates and distance in response
            rep['estimated_pickup_time'] = instance.estimated_pickup_time.isoformat() if instance.estimated_pickup_time else None
            rep['estimated_dropoff_time'] = instance.estimated_dropoff_time.isoformat() if instance.estimated_dropoff_time else None
            rep['total_distance'] = float(instance.total_distance) if instance.total_distance else None
        
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
