from rest_framework import serializers

from account.models import Rider, User, Vendor


class AdminUserListSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'is_active',
            'role',
            'phone_number',
            'profile_image',
            'is_verified',
            'created_at',
            'updated_at',
        ]

    def get_profile_image(self, obj):
        return obj.get_profile_image()


class AdminVendorListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            'id',
            'thumbnail',
            'thumbnail_url',
            'logo_url',
            'name',
            'email',
            'phone_number',
            'category',
            'is_active',
            'approval_status',
            'is_marketplace',
            'rating',
            'city',
            'state',
            'created_at',
            'updated_at',
        ]

    def get_category(self, obj):
        if not obj.category_id:
            return None
        return {
            'id': str(obj.category_id),
            'name': obj.category.name,
        }

    def get_thumbnail(self, obj):
        return obj.thumbnail_url or obj.logo_url or obj.user.get_profile_image()


class AdminRiderListSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    documents_uploaded_count = serializers.SerializerMethodField()

    class Meta:
        model = Rider
        fields = [
            'id',
            'user',
            'mode_of_transport',
            'vehicle_number',
            'vehicle_brand',
            'plate_number',
            'status',
            'document_status',
            'is_verified',
            'is_online',
            'is_in_house_rider',
            'documents_uploaded_count',
            'city',
            'state',
            'created_at',
            'updated_at',
        ]

    def get_user(self, obj):
        user = obj.user
        return {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            'is_active': user.is_active,
            'profile_image': user.get_profile_image(),
            'phone_number': user.phone_number,
        }

    def get_documents_uploaded_count(self, obj):
        document_fields = [
            'drivers_license_front',
            'drivers_license_back',
            'nin_front',
            'nin_back',
            'vehicle_insurance',
            'vehicle_registration',
        ]
        return sum(1 for field in document_fields if getattr(obj, field))
