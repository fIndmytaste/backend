import json
from multiprocessing import context
from rest_framework import serializers
from django.db.models import Q, Avg
from account.models import User, Vendor, VendorRating
from product.models import ProductVariant, UserFavoriteVendor, Product, ProductImage, Rating, SystemCategory, VendorCategory,ProductVariantCategory
from collections import defaultdict

from vendor.models import MarketPlace

class VendorImageUploadSerializer(serializers.Serializer):
    """
    Serializer for vendor image uploads (thumbnail and logo).
    """
    image = serializers.ImageField(required=True)
    
    def validate_image(self, value):
        """
        Validate the uploaded image file.
        """
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image file size cannot exceed 5MB.")
        
        # Check file format
        allowed_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if value.content_type not in allowed_formats:
            raise serializers.ValidationError("Only JPEG, PNG, and WebP images are allowed.")
        
        return value

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
        return obj.image_url


# class ProductSerializer(serializers.ModelSerializer):
#     discounted_price = serializers.SerializerMethodField()
#     images = ProductImageSerializer(many=True, read_only=True)  # Add images to the serialized product

#     class Meta:
#         model = Product
#         fields = [
#             'id','name','description','price',
#             'system_category','category','stock','is_active',
#             'is_delete','is_featured','views','discounted_price','images']

#     def to_representation(self, instance: Product):
#         images = ProductImage.objects.filter(product=instance)
#         data = super().to_representation(instance)
#         data['images'] = ProductImageSerializer(images, many=True, context=self.context).data
#         return data

#     def get_discounted_price(self, obj):
#         return obj.get_discounted_price()

    
    
#     def create(self, validated_data):
#         user = self.context['request'].user  # Get the current user from the request
#         vendor = Vendor.objects.get(user=user)  # Assuming Vendor is a model related to User

#         # Add the vendor to the validated data
#         validated_data['vendor'] = vendor

#         return super().create(validated_data)



class RatingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Rating
        fields = ['id', 'rating', 'comment', 'created_at', 'user_name', 'user_email', 'user_username']
        read_only_fields = ['id', 'created_at', 'user_name', 'user_email', 'user_username']


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        exclude = ['parent', 'vendor', 'views', 'purchases', 'created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    price_with_commission = serializers.SerializerMethodField()
    commission_amount = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    rating_distribution = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    has_purchased = serializers.SerializerMethodField()
    variants = ProductVariantSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price',
            'price_with_commission', 'commission_amount',
            'system_category', 'category', 'stock', 'is_active',
            'is_delete', 'is_featured', 'views', 'discounted_price', 'images',
            'average_rating', 'total_ratings', 'rating_distribution', 
            'recent_reviews', 'user_rating', 'has_purchased','variants'
        ]

    def to_representation(self, instance: Product):
        data = super().to_representation(instance)

        context = self.context
        addition_data = context.get('addition_serializer_data') or {}
        is_vendor = context.get('is_vendor', False) or addition_data.get('is_vendor', False)

        # --- Images: use prefetched cache if available ---
        if hasattr(instance, '_prefetched_objects_cache') and 'productimage_set' in instance._prefetched_objects_cache:
            images = instance.productimage_set.all()
        else:
            images = ProductImage.objects.filter(product=instance)
        data['images'] = ProductImageSerializer(images, many=True, context=self.context).data

        product_variant = []

        data['price'] = float(instance.get_price_with_commission()) if not is_vendor else float(instance.price)

        # --- New Structure: Use ProductVariantCategory (prefetched via productvariantcategory_set) ---
        if hasattr(instance, '_prefetched_objects_cache') and 'productvariantcategory_set' in instance._prefetched_objects_cache:
            variant_categories = list(instance.productvariantcategory_set.all())
        else:
            variant_categories = list(ProductVariantCategory.objects.filter(parent_product=instance))

        if variant_categories:
            for category in variant_categories:
                if hasattr(category, '_prefetched_objects_cache') and 'variants' in category._prefetched_objects_cache:
                    child_products = [v for v in category.variants.all() if v.is_active]
                else:
                    child_products = list(ProductVariant.objects.filter(category=category, is_active=True))

                if not child_products:
                    continue

                variants_list = [
                    {
                        "id": prod.id,
                        "name": prod.name,
                        "price": float(prod.price) if is_vendor else float(prod.get_price_with_commission()),
                    }
                    for prod in child_products
                ]

                product_variant.append({
                    "id": category.id,
                    "variant_category_name": category.category_name,
                    "select_at_least_one": category.select_at_least_one_variant_enabled,
                    "allow_multiple_quantity": category.allow_multiple_quantity,
                    "allow_multiple_variant_selection": category.allow_multiple_variant_selection,
                    "max_quantity_per_variant": category.max_quantity_per_variant,
                    "variants": variants_list
                })

        else:
            # --- Old Structure: Fallback to parent relationship + variant_category_name ---
            if hasattr(instance, '_prefetched_objects_cache') and 'variants' in instance._prefetched_objects_cache:
                variants_qs = list(instance.variants.all())
            else:
                variants_qs = list(Product.objects.filter(parent=instance))

            grouped_variants = defaultdict(list)
            for variant in variants_qs:
                key = variant.variant_category_name.strip() if variant.variant_category_name else "Uncategorized"
                price = float(variant.price) if is_vendor else (
                    float(variant.get_price_with_commission()) if hasattr(variant, 'get_price_with_commission') else float(variant.price)
                )
                grouped_variants[key].append({
                    "id": variant.id,
                    "name": variant.name,
                    "price": price,
                })

            product_variant = [
                {
                    "variant_category_name": category,
                    "select_at_least_one": instance.select_at_least_one_variant_enabled,
                    "variants": variants_list
                }
                for category, variants_list in grouped_variants.items()
            ]

        data['product_variant'] = product_variant

        # Clean up unused keys
        data.pop('variants', None)

        # --- Vendor Category: use select_related cache ---
        try:
            data['product_vendor_category'] = {
                'id': instance.vendor.category.id,
                'name': instance.vendor.category.name,
            }
        except Exception:
            data['product_vendor_category'] = None

        return data


    def get_discounted_price(self, obj):
        return obj.get_discounted_price()

    def get_price_with_commission(self, obj):
        """Return the product price including commission"""
        return float(obj.get_price_with_commission())

    def get_commission_amount(self, obj):
        """Return the commission amount for this product"""
        return float(obj.calculate_commission())

    def get_average_rating(self, obj):
        """Calculate average rating using prefetched ratings"""
        ratings = obj.ratings.all()
        if not ratings:
            return 0.00
        total = sum(r.rating for r in ratings)
        return round(total / len(ratings), 2)

    def get_total_ratings(self, obj):
        """Return total number of ratings using prefetched data"""
        return len(obj.ratings.all())

    def get_rating_distribution(self, obj):
        """Return rating distribution using prefetched ratings"""
        ratings = obj.ratings.all()
        distribution = {f'{i}_star': 0 for i in range(1, 6)}
        for r in ratings:
            star = min(5, max(1, int(r.rating)))
            distribution[f'{star}_star'] += 1
        return distribution

    def get_recent_reviews(self, obj):
        """Return the 5 most recent reviews with comments using prefetched data"""
        ratings = obj.ratings.all()
        recent = sorted(
            [r for r in ratings if r.comment],
            key=lambda r: r.created_at,
            reverse=True,
        )[:5]
        return RatingSerializer(recent, many=True).data

    def get_user_rating(self, obj):
        """Return the current user's rating using prefetched data"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            ratings = obj.ratings.all()
            for r in ratings:
                if r.user_id == request.user.id:
                    return RatingSerializer(r).data
        return None

    def get_has_purchased(self, obj):
        """Check if the current user has purchased this product"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return False  # Placeholder - implement based on your order model
        return False


class BuyerVendorProductSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    product_variant = serializers.SerializerMethodField()
    product_vendor_category = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'price',
            'system_category',
            'category',
            'stock',
            'is_active',
            'is_delete',
            'is_featured',
            'views',
            'discounted_price',
            'images',
            'average_rating',
            'total_ratings',
            'product_variant',
            'product_vendor_category',
        ]

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()

    def get_images(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'productimage_set' in obj._prefetched_objects_cache:
            images = obj.productimage_set.all()
        else:
            images = ProductImage.objects.filter(product=obj, is_active=True)
        return ProductImageSerializer(images, many=True, context=self.context).data

    def get_average_rating(self, obj):
        annotated = getattr(obj, 'average_rating_value', None)
        if annotated is not None:
            return round(float(annotated), 2)
        ratings = obj.ratings.all()
        if not ratings:
            return 0.0
        total = sum(r.rating for r in ratings)
        return round(total / len(ratings), 2)

    def get_total_ratings(self, obj):
        annotated = getattr(obj, 'total_ratings_value', None)
        if annotated is not None:
            return int(annotated)
        return len(obj.ratings.all())

    def get_product_variant(self, instance: Product):
        context = self.context
        addition_data = context.get('addition_serializer_data') or {}
        is_vendor = context.get('is_vendor', False) or addition_data.get('is_vendor', False)
        product_variant = []

        if hasattr(instance, '_prefetched_objects_cache') and 'productvariantcategory_set' in instance._prefetched_objects_cache:
            variant_categories = list(instance.productvariantcategory_set.all())
        else:
            variant_categories = list(ProductVariantCategory.objects.filter(parent_product=instance))

        if variant_categories:
            for category in variant_categories:
                if hasattr(category, '_prefetched_objects_cache') and 'variants' in category._prefetched_objects_cache:
                    child_products = [v for v in category.variants.all() if v.is_active]
                else:
                    child_products = list(ProductVariant.objects.filter(category=category, is_active=True))

                if not child_products:
                    continue

                product_variant.append({
                    "id": category.id,
                    "variant_category_name": category.category_name,
                    "select_at_least_one": category.select_at_least_one_variant_enabled,
                    "allow_multiple_quantity": category.allow_multiple_quantity,
                    "allow_multiple_variant_selection": category.allow_multiple_variant_selection,
                    "max_quantity_per_variant": category.max_quantity_per_variant,
                    "variants": [
                        {
                            "id": prod.id,
                            "name": prod.name,
                            "price": float(prod.price) if is_vendor else float(prod.get_price_with_commission()),
                        }
                        for prod in child_products
                    ]
                })
            return product_variant

        if hasattr(instance, '_prefetched_objects_cache') and 'variants' in instance._prefetched_objects_cache:
            variants_qs = list(instance.variants.all())
        else:
            variants_qs = list(Product.objects.filter(parent=instance, is_active=True))

        grouped_variants = defaultdict(list)
        for variant in variants_qs:
            key = variant.variant_category_name.strip() if variant.variant_category_name else "Uncategorized"
            price = float(variant.price) if is_vendor else float(variant.get_price_with_commission())
            grouped_variants[key].append({
                "id": variant.id,
                "name": variant.name,
                "price": price,
            })

        return [
            {
                "variant_category_name": category,
                "select_at_least_one": instance.select_at_least_one_variant_enabled,
                "variants": variants_list
            }
            for category, variants_list in grouped_variants.items()
        ]

    def get_product_vendor_category(self, instance):
        try:
            return {
                'id': instance.vendor.category.id,
                'name': instance.vendor.category.name,
            }
        except Exception:
            return None

    def to_representation(self, instance: Product):
        data = super().to_representation(instance)
        context = self.context
        addition_data = context.get('addition_serializer_data') or {}
        is_vendor = context.get('is_vendor', False) or addition_data.get('is_vendor', False)
        data['price'] = float(instance.price) if is_vendor else float(instance.get_price_with_commission())
        return data


    def create(self, validated_data):
        request = self.context['request']

        vendor = Vendor.objects.get(user=request.user)


        # Extract variants from validated_data if present
        variants_data = validated_data.pop('product_variant', [])
        variants_data_request = request.data.get("product_variant",[])
        select_at_least_one_variant_enabled = validated_data.get('select_at_least_one_variant', False)

        # Create the main product
        product = Product.objects.create(vendor=vendor, **validated_data)
        product.select_at_least_one_variant_enabled = select_at_least_one_variant_enabled
        product.save()


        # if variants_data_request and isinstance(variants_data_request, str):
        #     variants_data_request = eval(variants_data_request)
        
        # # Create each variant linked to this product
        # for variant_data in variants_data_request:
        #     if isinstance(variant_data, str):
        #         variant_data = eval(variant_data)

        if variants_data_request and isinstance(variants_data_request, str):
            variants_data_request = json.loads(variants_data_request)

        for variant_data in variants_data_request:
            if isinstance(variant_data, str):
                variant_data = json.loads(variant_data)

            category_name = variant_data.get('variant_category_name')
            variants_list = variant_data.get('variants',[])

            category = ProductVariantCategory.objects.create(
                category_name=category_name,
                parent_product=product,
            )
            category.select_at_least_one_variant_enabled = variant_data.get('select_at_least_one_variant', False)
            category.allow_multiple_quantity = variant_data.get('allow_multiple_quantity', False)
            category.allow_multiple_variant_selection = variant_data.get('allow_multiple_variant_selection', False)
            category.max_quantity_per_variant = variant_data.get('max_quantity_per_variant', None)
            category.save()

            for prod in variants_list:
                # todo remove this product creation duplication
                # child_product = Product.objects.create(
                #     parent=product,
                #     vendor=vendor,
                #     name=prod['name'],
                #     price=prod['price'],
                #     variant_category_name=category_name
                # )

                # category.child_products.add(child_product)

                ProductVariant.objects.create(
                    product=product,
                    category=category,
                    name=prod['name'],
                    price=prod['price'],
                )

        return product

    def update(self, instance, validated_data):
        request = self.context.get('request')

        # Extract variants to prevent errors on updating Product model directly
        validated_data.pop('product_variant', [])
        
        if request and 'select_at_least_one_variant' in request.data:
            val = request.data.get('select_at_least_one_variant')
            if isinstance(val, str):
                val = val.lower() in ['true', '1', 't', 'y', 'yes']
            instance.select_at_least_one_variant_enabled = val
        elif 'select_at_least_one_variant' in validated_data:
            instance.select_at_least_one_variant_enabled = validated_data.pop('select_at_least_one_variant')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if request and "product_variant" in request.data:
            variants_data_request = request.data.get("product_variant", [])

            if variants_data_request and isinstance(variants_data_request, str):
                try:
                    variants_data_request = json.loads(variants_data_request)
                except json.JSONDecodeError:
                    pass

            if isinstance(variants_data_request, list):
                processed_variant_ids = []

                for variant_data in variants_data_request:
                    if isinstance(variant_data, str):
                        try:
                            variant_data = json.loads(variant_data)
                        except json.JSONDecodeError:
                            continue

                    category_name = variant_data.get('variant_category_name')
                    category_id = variant_data.get('id')
                    variants_list = variant_data.get('variants', [])

                    if not category_name:
                        continue
                        
                    category = None
                    if category_id:
                        try:
                            category = ProductVariantCategory.objects.get(id=category_id, parent_product=instance)
                            category.category_name = category_name
                        except Exception:
                            pass

                    if not category:
                        # Fetch or create the category based on name and parent product
                        category, _ = ProductVariantCategory.objects.get_or_create(
                            category_name=category_name,
                            parent_product=instance,
                        )

                    def parse_bool(val, default):
                        if isinstance(val, str):
                            return val.lower() in ['true', '1', 't', 'y', 'yes']
                        return bool(val) if val is not None else default

                    category.select_at_least_one_variant_enabled = parse_bool(variant_data.get('select_at_least_one_variant'), category.select_at_least_one_variant_enabled)
                    category.allow_multiple_quantity = parse_bool(variant_data.get('allow_multiple_quantity'), category.allow_multiple_quantity)
                    category.allow_multiple_variant_selection = parse_bool(variant_data.get('allow_multiple_variant_selection'), category.allow_multiple_variant_selection)
                    
                    max_qty = variant_data.get('max_quantity_per_variant')
                    if max_qty is not None and str(max_qty).isdigit():
                        category.max_quantity_per_variant = int(max_qty)
                    else:
                        category.max_quantity_per_variant = None

                    category.save()

                    for prod in variants_list:
                        variant_name = prod.get('name')
                        variant_price = prod.get('price', 0)
                        variant_id = prod.get('id')
                        
                        if not variant_name:
                            continue

                        variant = None
                        if variant_id:
                            try:
                                variant = ProductVariant.objects.get(id=variant_id, product=instance)
                            except ProductVariant.DoesNotExist:
                                pass
                                
                        if not variant:
                            variant = ProductVariant.objects.filter(name=variant_name, product=instance, category=category).first()

                        if variant:
                            variant.name = variant_name
                            variant.price = variant_price
                            variant.category = category
                            variant.is_active = True
                            variant.save()
                        else:
                            variant = ProductVariant.objects.create(
                                product=instance,
                                category=category,
                                name=variant_name,
                                price=variant_price,
                            )
                        
                        processed_variant_ids.append(variant.id)

                # Soft delete any product variants that were not passed in the request
                ProductVariant.objects.filter(product=instance).exclude(id__in=processed_variant_ids).update(is_active=False)

        return instance



class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFavoriteVendor
        fields = '__all__'


# class VendorSerializer(serializers.ModelSerializer):
#     thumbnail = serializers.SerializerMethodField()
#     logo = serializers.SerializerMethodField()
#     class Meta:
#         model = Vendor
#         fields = '__all__'


#     def get_thumbnail(self, obj):
#         request = self.context.get('request')
#         return obj.thumbnail.url if obj.thumbnail else None
    

#     def get_logo(self, obj):
#         request = self.context.get('request')
#         return obj.logo.url if obj.logo else None





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
    marketplace_id = serializers.UUIDField(required=False)




class VendorRatingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = VendorRating
        fields = ['id', 'rating', 'comment', 'created_at', 'user_name', 'user_email']
        read_only_fields = ['id', 'created_at', 'user_name', 'user_email']

class VendorInlineUserSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField() 
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_active', "profile_image"]



    def get_profile_image(self, obj):
        return obj.get_profile_image()

class VendorSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    user = VendorInlineUserSerializer()
    category = SystemCategorySerializer()
    
    class Meta:
        model = Vendor
        fields = '__all__'
        extra_fields = ['average_rating', 'total_ratings', 'recent_reviews', 'user_rating', 'open_day', 'close_day']

    def get_fields(self):
        fields = super().get_fields()
        # Add the extra fields to the actual fields
        for field_name in self.Meta.extra_fields:
            if field_name in fields:
                continue
        return fields

    def get_thumbnail(self, obj:Vendor):
        return obj.thumbnail_url
    
    def get_logo(self, obj:Vendor):
        return obj.logo_url
    
    def get_average_rating(self, obj:Vendor):
        """Calculate and return the average rating for the vendor"""
        avg_rating = obj.ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(float(avg_rating), 2) if avg_rating else 0.00
    
    def get_total_ratings(self, obj):
        """Return total number of ratings for the vendor"""
        return obj.ratings.count()
    
    def get_recent_reviews(self, obj):
        """Return the 5 most recent reviews with comments"""
        recent_ratings = obj.ratings.filter(comment__isnull=False).exclude(comment='').order_by('-created_at')[:5]
        return VendorRatingSerializer(recent_ratings, many=True).data
    
    def get_user_rating(self, obj):
        """Return the current user's rating for this vendor if they have rated it"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            try:
                user_rating = obj.ratings.get(user=request.user)
                return VendorRatingSerializer(user_rating).data
            except VendorRating.DoesNotExist:
                return None
        return None
    

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        try:
            if request and request.user.is_authenticated:
                return UserFavoriteVendor.objects.filter(user=request.user, vendor=obj).exists()
            return False
        except:
            return False

    def to_representation(self, instance):
        from product.models import Order
        from django.db.models import Avg, F, ExpressionWrapper, DurationField
        from django.utils import timezone
        from datetime import timedelta

        data = super().to_representation(instance)

        if MarketPlace.objects.filter(vendors=instance).exists():
            # Marketplace: fixed 24-48 hr window — use the vendor's stored value if
            # admin has customised it, otherwise default to 48 h.
            stored = instance.estimated_delivery_time
            if stored and stored > timedelta(hours=1):
                # Already customised by admin — keep it as-is.
                pass
            else:
                data['estimated_delivery_time'] = '2 days, 0:00:00'
            data['is_marketplace_vendor'] = True
        else:
            # Regular vendor: compute average actual delivery duration from the
            # last 50 delivered orders that have both timestamps.
            recent_orders = (
                Order.objects
                .filter(
                    vendor=instance,
                    status='delivered',
                    actual_delivery_time__isnull=False,
                    actual_pickup_time__isnull=False,
                )
                .order_by('-actual_delivery_time')[:50]
            )

            durations = []
            for order in recent_orders:
                try:
                    duration = order.actual_delivery_time - order.actual_pickup_time
                    if timedelta(minutes=5) <= duration <= timedelta(hours=6):
                        durations.append(duration)
                except Exception:
                    pass

            if durations:
                avg_seconds = sum(d.total_seconds() for d in durations) / len(durations)
                # Round up to nearest 5 minutes
                rounded = timedelta(seconds=round(avg_seconds / 300) * 300)
                # Format as Django DurationField string HH:MM:SS
                total_secs = int(rounded.total_seconds())
                hours, rem = divmod(total_secs, 3600)
                minutes, secs = divmod(rem, 60)
                data['estimated_delivery_time'] = f'{hours}:{minutes:02d}:{secs:02d}'
            # else: keep the stored value from the model (admin can set it manually)

            data['is_marketplace_vendor'] = False

        return data


class VendorRatingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating vendor ratings"""
    
    class Meta:
        model = VendorRating
        fields = ['vendor', 'rating', 'comment']
    
    def validate_rating(self, value):
        """Validate that rating is between 0 and 5"""
        if value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be between 0 and 5")
        return value
    
    def create(self, validated_data):
        """Create or update rating for a vendor by a user"""
        user = self.context['request'].user
        vendor = validated_data['vendor']
        
        # Try to get existing rating, if exists update it, otherwise create new
        rating, created = VendorRating.objects.update_or_create(
            vendor=vendor,
            user=user,
            defaults={
                'rating': validated_data['rating'],
                'comment': validated_data.get('comment', '')
            }
        )
        
        # Update vendor's overall rating
        self.update_vendor_rating(vendor)
        
        return rating
    
    def update_vendor_rating(self, vendor):
        """Update the vendor's overall rating based on all ratings"""
        avg_rating = vendor.ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
        if avg_rating:
            vendor.rating = round(float(avg_rating), 2)
            vendor.save(update_fields=['rating'])





class MarketPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketPlace
        fields = '__all__'




class VendorOrderActionSerializer(serializers.Serializer):
    ACTION_CHOICES = [
        ('accept', 'Accept'),
        ('reject', 'Reject'),
    ]

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
