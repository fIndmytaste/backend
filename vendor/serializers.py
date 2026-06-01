import json
from multiprocessing import context
from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers
from django.db.models import Q, Avg
from account.models import User, Vendor, VendorRating
from product.models import Order, ProductVariant, UserFavoriteVendor, Product, ProductImage, Rating, SystemCategory, VendorCategory, ProductVariantCategory
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
    vendor_count = serializers.SerializerMethodField()
    has_vendors = serializers.SerializerMethodField()

    class Meta:
        model = SystemCategory
        fields = '__all__'

    def _count_vendors(self, obj):
        # Fast path: the view annotated the queryset with `active_vendor_count`.
        annotated = getattr(obj, 'active_vendor_count', None)
        if annotated is not None:
            return annotated
        # Fallback for callers that don't annotate (kept for safety; logs help
        # spot accidental N+1 reintroductions).
        from account.models import Vendor
        return Vendor.objects.filter(
            category_id=obj.id,
            is_active=True,
        ).count()

    def get_vendor_count(self, obj):
        return self._count_vendors(obj)

    def get_has_vendors(self, obj):
        return self._count_vendors(obj) > 0


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


def _variant_stock_value(data):
    try:
        return max(0, int(data.get('stock', 0) or 0))
    except (TypeError, ValueError):
        return 0


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
    variants = ProductVariantSerializer(many=True, read_only=True)

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
            images = [
                image for image in instance.productimage_set.all()
                if image.is_active and image.image_url
            ]
        else:
            images = ProductImage.objects.filter(product=instance, is_active=True).exclude(image_url='')
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
                        "stock": prod.stock,
                        "track_stock": prod.track_stock,
                        "is_available": (not prod.track_stock) or prod.stock > 0,
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
                    "stock": variant.stock,
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
        context = self.context or {}
        addition_data = context.get('addition_serializer_data') or {}
        is_vendor = context.get('is_vendor', False) or addition_data.get('is_vendor', False)
        price = obj.get_discounted_price() if is_vendor else obj.get_discounted_price_with_service_charge()
        return float(price)

    def get_price_with_commission(self, obj):
        """Return the product price including commission"""
        return float(obj.get_price_with_commission())

    def get_commission_amount(self, obj):
        """Return the commission amount for this product"""
        return float(obj.calculate_commission())

    def _get_ratings_cached(self, obj):
        """Evaluate ratings once and cache on the instance to avoid repeat DB hits."""
        if not hasattr(obj, '_ratings_cache'):
            obj._ratings_cache = list(obj.ratings.all())
        return obj._ratings_cache

    def get_average_rating(self, obj):
        ratings = self._get_ratings_cached(obj)
        if not ratings:
            return 0.00
        return round(sum(r.rating for r in ratings) / len(ratings), 2)

    def get_total_ratings(self, obj):
        return len(self._get_ratings_cached(obj))

    def get_rating_distribution(self, obj):
        distribution = {f'{i}_star': 0 for i in range(1, 6)}
        for r in self._get_ratings_cached(obj):
            star = min(5, max(1, int(r.rating)))
            distribution[f'{star}_star'] += 1
        return distribution

    def get_recent_reviews(self, obj):
        ratings = self._get_ratings_cached(obj)
        recent = sorted(
            [r for r in ratings if r.comment],
            key=lambda r: r.created_at,
            reverse=True,
        )[:5]
        return RatingSerializer(recent, many=True).data

    def get_user_rating(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            for r in self._get_ratings_cached(obj):
                if r.user_id == request.user.id:
                    return RatingSerializer(r).data
        return None

    def get_has_purchased(self, obj):
        """Check if the current user has purchased this product"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return False  # Placeholder - implement based on your order model
        return False

    def create(self, validated_data):
        request = self.context['request']
        vendor = Vendor.objects.get(user=request.user)

        validated_data.pop('product_variant', [])
        validated_data.pop('select_at_least_one_variant', None)

        product = Product.objects.create(vendor=vendor, **validated_data)

        raw_variants = request.data.get("product_variant", "")
        self._save_variants_for_product(product, raw_variants)

        return product

    def _save_variants_for_product(self, product, raw_variants):
        """Parse and save ProductVariantCategory + ProductVariant rows for a product."""
        if not raw_variants:
            return

        if isinstance(raw_variants, str):
            try:
                variants_data_request = json.loads(raw_variants)
            except (json.JSONDecodeError, ValueError):
                return
        elif isinstance(raw_variants, list):
            variants_data_request = raw_variants
        else:
            return

        for variant_data in variants_data_request:
            if isinstance(variant_data, str):
                try:
                    variant_data = json.loads(variant_data)
                except (json.JSONDecodeError, ValueError):
                    continue

            category_name = variant_data.get('variant_category_name', '').strip()
            variants_list = variant_data.get('variants', [])

            if not category_name:
                continue

            category = ProductVariantCategory.objects.create(
                category_name=category_name,
                parent_product=product,
                select_at_least_one_variant_enabled=variant_data.get('select_at_least_one_variant', False),
                allow_multiple_quantity=variant_data.get('allow_multiple_quantity', False),
                allow_multiple_variant_selection=variant_data.get('allow_multiple_variant_selection', False),
                max_quantity_per_variant=variant_data.get('max_quantity_per_variant') or None,
            )

            for v in variants_list:
                if isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except (json.JSONDecodeError, ValueError):
                        continue
                vname = v.get('name', '').strip()
                vprice = v.get('price', 0)
                vstock = _variant_stock_value(v)
                if not vname:
                    continue
                ProductVariant.objects.create(
                    product=product,
                    category=category,
                    name=vname,
                    price=vprice,
                    stock=vstock,
                    track_stock=vstock > 0,
                )

    def update(self, instance, validated_data):
        request = self.context.get('request')

        validated_data.pop('product_variant', None)
        validated_data.pop('variants', None)
        validated_data.pop('select_at_least_one_variant', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if not request:
            return instance

        raw_variants = request.data.get("product_variant", "")
        if not raw_variants:
            return instance

        if isinstance(raw_variants, str):
            try:
                variants_data_request = json.loads(raw_variants)
            except (json.JSONDecodeError, ValueError):
                return instance
        elif isinstance(raw_variants, list):
            variants_data_request = raw_variants
        else:
            return instance

        if not isinstance(variants_data_request, list):
            return instance

        processed_variant_ids = []

        for variant_data in variants_data_request:
            if isinstance(variant_data, str):
                try:
                    variant_data = json.loads(variant_data)
                except (json.JSONDecodeError, ValueError):
                    continue

            category_name = (variant_data.get('variant_category_name') or '').strip()
            category_id = variant_data.get('id', '')
            variants_list = variant_data.get('variants', [])

            if not category_name:
                continue

            # Try to find existing category by id, fall back to name match
            category = None
            if category_id:
                try:
                    category = ProductVariantCategory.objects.get(id=category_id, parent_product=instance)
                    category.category_name = category_name
                except (ProductVariantCategory.DoesNotExist, Exception):
                    pass

            if not category:
                category, _ = ProductVariantCategory.objects.get_or_create(
                    category_name=category_name,
                    parent_product=instance,
                )

            category.select_at_least_one_variant_enabled = bool(variant_data.get('select_at_least_one_variant', False))
            category.allow_multiple_quantity = bool(variant_data.get('allow_multiple_quantity', False))
            category.allow_multiple_variant_selection = bool(variant_data.get('allow_multiple_variant_selection', False))
            max_qty = variant_data.get('max_quantity_per_variant')
            category.max_quantity_per_variant = int(max_qty) if max_qty and str(max_qty).isdigit() else None
            category.save()

            for v in variants_list:
                if isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except (json.JSONDecodeError, ValueError):
                        continue

                variant_name = (v.get('name') or '').strip()
                variant_price = v.get('price', 0)
                variant_id = v.get('id', '')
                variant_stock_provided = 'stock' in v
                variant_stock = _variant_stock_value(v)

                if not variant_name:
                    continue

                variant = None
                if variant_id:
                    try:
                        variant = ProductVariant.objects.get(id=variant_id, product=instance)
                    except ProductVariant.DoesNotExist:
                        pass

                if not variant:
                    variant = ProductVariant.objects.filter(
                        name=variant_name, product=instance, category=category
                    ).first()

                if variant:
                    variant.name = variant_name
                    variant.price = variant_price
                    variant.category = category
                    variant.is_active = True
                    if variant_stock_provided:
                        variant.stock = variant_stock
                        variant.track_stock = variant_stock > 0
                    variant.save()
                else:
                    variant = ProductVariant.objects.create(
                        product=instance,
                        category=category,
                        name=variant_name,
                        price=variant_price,
                        stock=variant_stock,
                        track_stock=variant_stock > 0,
                    )

                processed_variant_ids.append(variant.id)

        # Soft-delete variants not in this update
        ProductVariant.objects.filter(product=instance).exclude(
            id__in=processed_variant_ids
        ).update(is_active=False)

        return instance


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
        context = self.context or {}
        addition_data = context.get('addition_serializer_data') or {}
        is_vendor = context.get('is_vendor', False) or addition_data.get('is_vendor', False)
        price = obj.get_discounted_price() if is_vendor else obj.get_discounted_price_with_service_charge()
        return float(price)

    def _price_with_commission(self, product, base_price):
        """Return base_price + flat service charge for the given product."""
        if hasattr(product, 'get_price_with_commission'):
            return product.get_price_with_commission()
        base = Decimal(str(base_price or 0))
        charge = product.get_service_charge(base)
        return (base + charge).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_images(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'productimage_set' in obj._prefetched_objects_cache:
            images = [
                image for image in obj.productimage_set.all()
                if image.is_active and image.image_url
            ]
        else:
            images = ProductImage.objects.filter(product=obj, is_active=True).exclude(image_url='')
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
                            "price": float(prod.price) if is_vendor else float(self._price_with_commission(prod, prod.price)),
                            "stock": prod.stock,
                            "track_stock": prod.track_stock,
                            "is_available": (not prod.track_stock) or prod.stock > 0,
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
            price = float(variant.price) if is_vendor else float(self._price_with_commission(variant, variant.price))
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
        data['price'] = float(instance.price) if is_vendor else float(self._price_with_commission(instance, instance.price))
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
                    stock=_variant_stock_value(prod),
                    track_stock=_variant_stock_value(prod) > 0,
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
                        variant_stock_provided = 'stock' in prod
                        variant_stock = _variant_stock_value(prod)
                        
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
                            if variant_stock_provided:
                                variant.stock = variant_stock
                                variant.track_stock = variant_stock > 0
                            variant.save()
                        else:
                            variant = ProductVariant.objects.create(
                                product=instance,
                                category=category,
                                name=variant_name,
                                price=variant_price,
                                stock=variant_stock,
                                track_stock=variant_stock > 0,
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
    
    def _get_prefetched_ratings(self, obj):
        """Return prefetched ratings list if available, else evaluate queryset once."""
        if hasattr(obj, '_prefetched_objects_cache') and 'ratings' in obj._prefetched_objects_cache:
            return list(obj.ratings.all())
        if not hasattr(obj, '_ratings_cache'):
            obj._ratings_cache = list(obj.ratings.all())
        return obj._ratings_cache

    def get_average_rating(self, obj: Vendor):
        # Prefer annotated value set by list views (zero DB cost).
        annotated = getattr(obj, '_avg_rating', None)
        if annotated is not None:
            return round(float(annotated), 2)
        ratings = self._get_prefetched_ratings(obj)
        if not ratings:
            return 0.00
        return round(sum(float(r.rating) for r in ratings) / len(ratings), 2)

    def get_total_ratings(self, obj):
        annotated = getattr(obj, '_total_ratings', None)
        if annotated is not None:
            return annotated
        return len(self._get_prefetched_ratings(obj))

    def get_recent_reviews(self, obj):
        ratings = self._get_prefetched_ratings(obj)
        with_comments = [r for r in ratings if r.comment]
        with_comments.sort(key=lambda r: r.created_at, reverse=True)
        return VendorRatingSerializer(with_comments[:5], many=True).data

    def get_user_rating(self, obj):
        request = self.context.get('request')
        if not (request and request.user and request.user.is_authenticated):
            return None
        ratings = self._get_prefetched_ratings(obj)
        for r in ratings:
            if r.user_id == request.user.id:
                return VendorRatingSerializer(r).data
        return None

    def get_is_favorite(self, obj):
        # Prefer annotated boolean set by list views (zero DB cost).
        annotated = getattr(obj, '_is_favorite', None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get('request')
        try:
            if request and request.user.is_authenticated:
                return UserFavoriteVendor.objects.filter(user=request.user, vendor=obj).exists()
            return False
        except Exception:
            return False

    def to_representation(self, instance):
        from product.models import Order
        from django.db.models import Avg, F, ExpressionWrapper, DurationField
        from django.utils import timezone
        from datetime import timedelta

        data = super().to_representation(instance)

        from django.core.cache import cache as django_cache

        # Prefer annotated flag or prefetched reverse relation — avoids a per-vendor query.
        if hasattr(instance, '_is_marketplace_member'):
            is_marketplace = instance._is_marketplace_member
        elif hasattr(instance, '_prefetched_objects_cache') and 'marketplace_set' in instance._prefetched_objects_cache:
            is_marketplace = bool(list(instance.marketplace_set.all()))
        else:
            is_marketplace = MarketPlace.objects.filter(vendors=instance).exists()

        if is_marketplace:
            # Marketplace: fixed 24-48 hr window — use the vendor's stored value if
            # admin has customised it, otherwise default to 48 h.
            stored = instance.estimated_delivery_time
            if not (stored and stored > timedelta(hours=1)):
                data['estimated_delivery_time'] = '2 days, 0:00:00'
            data['is_marketplace_vendor'] = True
        else:
            # Regular vendor: compute average actual delivery duration from the
            # last 50 delivered orders. Cache per-vendor for 30 minutes so list
            # responses don't fire 50 * N queries.
            cache_key = f'vendor_avg_delivery_{instance.id}'
            cached_time = django_cache.get(cache_key)
            if cached_time is not None:
                if cached_time:
                    data['estimated_delivery_time'] = cached_time
            else:
                recent_orders = (
                    Order.objects
                    .filter(
                        vendor=instance,
                        status='delivered',
                        actual_delivery_time__isnull=False,
                        actual_pickup_time__isnull=False,
                    )
                    .only('actual_delivery_time', 'actual_pickup_time')
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

                delivery_time_str = ''
                if durations:
                    avg_seconds = sum(d.total_seconds() for d in durations) / len(durations)
                    rounded = timedelta(seconds=round(avg_seconds / 300) * 300)
                    total_secs = int(rounded.total_seconds())
                    hours, rem = divmod(total_secs, 3600)
                    minutes, secs = divmod(rem, 60)
                    delivery_time_str = f'{hours}:{minutes:02d}:{secs:02d}'
                    data['estimated_delivery_time'] = delivery_time_str

                # Cache result (empty string means "no data — use model default")
                django_cache.set(cache_key, delivery_time_str, timeout=1800)

            data['is_marketplace_vendor'] = False

        return data


class BuyerVendorCardSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    category = SystemCategorySerializer()
    is_marketplace_vendor = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            'id',
            'name',
            'email',
            'phone_number',
            'country',
            'state',
            'city',
            'address',
            'location_latitude',
            'location_longitude',
            'description',
            'logo',
            'thumbnail',
            'rating',
            'average_rating',
            'total_ratings',
            'recent_reviews',
            'user_rating',
            'is_favorite',
            'is_active',
            'is_featured',
            'created_at',
            'updated_at',
            'open_time',
            'close_time',
            'open_day',
            'close_day',
            'estimated_delivery_time',
            'starting_delivery_price',
            'category',
            'is_marketplace_vendor',
        ]

    def get_thumbnail(self, obj: Vendor):
        return obj.thumbnail_url

    def get_logo(self, obj: Vendor):
        return obj.logo_url

    def get_average_rating(self, obj: Vendor):
        annotated = getattr(obj, '_avg_rating', None)
        if annotated is not None:
            return round(float(annotated), 2)
        if obj.rating is not None:
            return round(float(obj.rating), 2)
        return 0.0

    def get_total_ratings(self, obj: Vendor):
        annotated = getattr(obj, '_total_ratings', None)
        return int(annotated or 0)

    def get_recent_reviews(self, obj: Vendor):
        return []

    def get_user_rating(self, obj: Vendor):
        return None

    def get_is_favorite(self, obj: Vendor):
        annotated = getattr(obj, '_is_favorite', None)
        if annotated is not None:
            return bool(annotated)
        return False

    def get_is_marketplace_vendor(self, obj: Vendor):
        annotated = getattr(obj, '_is_marketplace_member', None)
        if annotated is not None:
            return bool(annotated)
        return bool(getattr(obj, 'is_marketplace', False))


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


class VendorOrderSerializer(serializers.ModelSerializer):
    """
    Order serializer for vendor-facing views.

    Prices shown here are the vendor's original prices — commission is NOT
    included. The customer pays product.price + commission; the vendor should
    only see what they actually earn per item.
    """

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'status', 'total_amount', 'promo_discount_amount',
            'payment_status', 'payment_method', 'items', 'note', 'address',
            'actual_delivery_time', 'actual_pickup_time', 'track_id',
            'delivery_fee', 'delivery_otp', 'location_latitude',
            'location_longitude', 'delivery_status', 'delivered_at',
            'created_at', 'updated_at',
        ]

    def to_representation(self, instance):

        rep = {}
        # Populate simple scalar fields manually (avoids inheriting
        # the commission-inflated whole_price from OrderSerializer).
        for field in [
            'id', 'status', 'payment_status', 'payment_method', 'note',
            'address', 'actual_delivery_time', 'actual_pickup_time',
            'track_id', 'delivery_otp', 'location_latitude',
            'location_longitude', 'delivery_status', 'created_at',
            'updated_at', 'delivered_at',
        ]:
            value = getattr(instance, field, None)
            rep[field] = str(value) if value is not None else None

        rep['delivery_fee'] = float(instance.delivery_fee or 0)
        rep['promo_discount_amount'] = float(instance.promo_discount_amount or 0)

        # User info
        if instance.user:
            rep['user'] = {
                'id': str(instance.user.id),
                'full_name': instance.user.full_name,
                'email': instance.user.email,
                'phone_number': instance.user.phone_number,
            }
        else:
            rep['user'] = None

        # Build items using vendor prices (product.price, not price_with_commission).
        # Each unique (product + variant combination) becomes its own line item so
        # that orders with the same product but different variants are shown separately.
        items_list = []
        items = list(instance.items.all())

        vendor_items_total = 0.0
        for item in items:
            product = item.product
            product_images = list(product.productimage_set.all()) if hasattr(product, 'productimage_set') else []
            variant_selections = list(item.variant_selections.all()) if hasattr(item, 'variant_selections') else []

            variants_data = []
            variant_total = 0.0
            for vs in variant_selections:
                variant_obj = vs.variant
                variant_price = float(variant_obj.price)
                variant_total += variant_price * vs.quantity
                variants_data.append({
                    'id': str(variant_obj.id),
                    'variant_category_name': getattr(
                        getattr(variant_obj, 'category', None),
                        'category_name', None
                    ),
                    'name': variant_obj.name,
                    'price': variant_price,
                    'quantity': vs.quantity,
                })

            item_price = float(product.price)
            vendor_items_total += item_price * item.quantity + variant_total

            items_list.append({
                'product': {
                    'id': str(product.id),
                    'name': product.name,
                    'price': item_price,
                    'images': ProductImageSerializer(product_images, many=True).data,
                },
                'price': item_price,
                'unit_price': item_price,
                'quantity': item.quantity,
                'variants': variants_data,
            })

        rep['items'] = items_list

        delivery_fee = float(instance.delivery_fee or 0)
        discount = float(instance.promo_discount_amount or 0)

        rep['items_total'] = round(vendor_items_total, 2)
        rep['total_amount'] = round(max(0.0, vendor_items_total + delivery_fee - discount), 2)
        rep['service_fee'] = 0  # commission not shown to vendor

        # Rider info (shown in track delivery screen)
        if instance.rider:
            rep['rider'] = {
                'id': str(instance.rider.id),
                'name': instance.rider.user.full_name or '',
                'phone': instance.rider.user.phone_number or '',
            }
        else:
            rep['rider'] = None

        return rep
