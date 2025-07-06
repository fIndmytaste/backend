from rest_framework import serializers
from django.db.models import Q, Avg
from account.models import User, Vendor, VendorRating
from product.models import Favorite, Product, ProductImage, Rating, SystemCategory, VendorCategory
from collections import defaultdict
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
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


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
            'system_category', 'category', 'stock', 'is_active',
            'is_delete', 'is_featured', 'views', 'discounted_price', 'images',
            'average_rating', 'total_ratings', 'rating_distribution', 
            'recent_reviews', 'user_rating', 'has_purchased','variants'
        ]

    def to_representation(self, instance: Product):
        data = super().to_representation(instance)

        # Serialize images as before (optional if you want custom queryset)
        images = ProductImage.objects.filter(product=instance)
        data['images'] = ProductImageSerializer(images, many=True, context=self.context).data

        # Get all variants (assuming variants are Products with parent=instance)
        variants_qs = Product.objects.filter(parent=instance)

        # Group variants by variant_category_name
        grouped_variants = defaultdict(list)
        for variant in variants_qs:
            key = variant.variant_category_name.strip() if variant.variant_category_name else "Uncategorized"
            grouped_variants[key].append({
                "name": variant.name,
                "price": variant.price,
            })

        # Format into the product_variant list
        product_variant = [
            {
                "variant_category_name": category,
                "variants": variants_list
            }
            for category, variants_list in grouped_variants.items()
        ]

        data['product_variant'] = product_variant

        data.pop('variants', None)

        # add the vendor category to the object
        try:
            data['product_vendor_category'] = {
                'id': instance.vendor_category.id,
                'name': instance.vendor_category.name,
            }
        except:
            data['product_vendor_category'] = None 

        return data
    

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()

    def get_average_rating(self, obj):
        """Calculate and return the average rating for the product"""
        avg_rating = obj.ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(float(avg_rating), 2) if avg_rating else 0.00

    def get_total_ratings(self, obj):
        """Return total number of ratings for the product"""
        return obj.ratings.count()

    def get_rating_distribution(self, obj):
        """Return rating distribution (1-5 stars count)"""
        distribution = {}
        for i in range(1, 6):
            count = obj.ratings.filter(rating__gte=i, rating__lt=i+1).count()
            distribution[f'{i}_star'] = count
        return distribution

    def get_recent_reviews(self, obj):
        """Return the 5 most recent reviews with comments"""
        recent_ratings = obj.ratings.filter(
            comment__isnull=False
        ).exclude(comment='').order_by('-created_at')[:5]
        return RatingSerializer(recent_ratings, many=True).data

    def get_user_rating(self, obj):
        """Return the current user's rating for this product if they have rated it"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                user_rating = obj.ratings.get(user=request.user)
                return RatingSerializer(user_rating).data
            except Rating.DoesNotExist:
                return None
        return None

    def get_has_purchased(self, obj):
        """Check if the current user has purchased this product"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # You'll need to implement this based on your Order/Purchase model
            # Example: return Order.objects.filter(user=request.user, items__product=obj).exists()
            return False  # Placeholder - implement based on your order model
        return False

    # def create(self, validated_data):
    #     user = self.context['request'].user
    #     vendor = Vendor.objects.get(user=user)
    #     validated_data['vendor'] = vendor
    #     return super().create(validated_data)

    def create(self, validated_data):
        request = self.context['request']

        vendor = Vendor.objects.get(user=request.user)


        # Extract variants from validated_data if present
        variants_data = validated_data.pop('product_variant', [])
        variants_data_request = request.data.get("product_variant",[])



        # Create the main product
        product = Product.objects.create(vendor=vendor, **validated_data)


        if variants_data_request and isinstance(variants_data_request, str):
            variants_data_request = eval(variants_data_request)
        
        # Create each variant linked to this product
        for variant_data in variants_data_request:
            if isinstance(variant_data, str):
                variant_data = eval(variant_data)

            variant_category_name = variant_data.get('variant_category_name')
            variants_list = variant_data.get('variants',[])
            for prod in variants_list:
                p = Product.objects.create(
                    parent=product,
                    vendor=vendor,
                    name=prod['name'],
                    price=prod['price'],
                    variant_category_name=variant_category_name
                )

        return product




class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
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
        return obj.profile_image.url if obj.profile_image else None

class VendorSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    user = VendorInlineUserSerializer()
    category = SystemCategorySerializer()
    
    class Meta:
        model = Vendor
        fields = '__all__'
        extra_fields = ['average_rating', 'total_ratings', 'recent_reviews', 'user_rating']

    def get_fields(self):
        fields = super().get_fields()
        # Add the extra fields to the actual fields
        for field_name in self.Meta.extra_fields:
            if field_name in fields:
                continue
        return fields

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        return obj.thumbnail.url if obj.thumbnail else None
    
    def get_logo(self, obj):
        request = self.context.get('request')
        return obj.logo.url if obj.logo else None
    
    def get_average_rating(self, obj):
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
        if request and request.user.is_authenticated:
            try:
                user_rating = obj.ratings.get(user=request.user)
                return VendorRatingSerializer(user_rating).data
            except VendorRating.DoesNotExist:
                return None
        return None


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




