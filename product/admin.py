from django.contrib import admin
from .models import (
    SystemCategory, VendorCategory, Product, ProductImage,
    Order, OrderItem, Rating, UserFavoriteVendor, ProductView, DeliveryTracking,
    PlatformSettings, DeliveryZone, EstateGatePass
)
from .promo_models import PromoCode, PromoUsage

# Inline for OrderItem
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'total_price')

    def total_price(self, obj):
        return obj.total_price()

# Inline for ProductImage
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

# SystemCategory Admin
@admin.register(SystemCategory)
class SystemCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_special_pricing', 'commission_percentage', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_filter = ('is_special_pricing',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'name_key', 'logo', 'description')
        }),
        ('Pricing Settings', {
            'fields': ('is_special_pricing', 'commission_percentage', 'delivery_percentage_off'),
            'description': 'Commission/discount percentage overrides platform default for this category. Leave blank to use platform default.'
        }),
        ('Stock Settings', {
            'fields': ('is_stock',)
        }),
    )

# VendorCategory Admin
@admin.register(VendorCategory)
class VendorCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'vendor__user__username')

# Product Admin
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'stock', 'is_active', 'is_featured', 'views', 'purchases')
    list_filter = ('is_active', 'is_featured', 'vendor')
    search_fields = ('name', 'vendor__user__username')
    inlines = [ProductImageInline]
    readonly_fields = ('views', 'purchases', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'price', 'stock', 'vendor', 'system_category', 'category')
        }),
        ('Status & Flags', {
            'fields': ('is_active', 'is_delete', 'is_featured')
        }),
        ('Discount', {
            'fields': ('apply_discount', 'discount_percentage', 'discount_start_date', 'discount_end_date')
        }),
        ('Stats', {
            'fields': ('views', 'purchases', 'created_at', 'updated_at')
        }),
    )

# Order Admin
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'vendor', 'status', 'payment_status', 'total_amount', 'created_at')
    list_filter = ('status', 'payment_status', 'vendor')
    search_fields = ('id', 'user__username', 'track_id')
    inlines = [OrderItemInline]
    readonly_fields = (
        'track_id', 'created_at', 'updated_at', 
        'actual_pickup_time', 'actual_delivery_time'
    )

# Rating Admin
@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    search_fields = ('product__name', 'user__username')
    readonly_fields = ('created_at',)

# Favorite Admin
@admin.register(UserFavoriteVendor)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'vendor', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at',)

# ProductView Admin
@admin.register(ProductView)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('created_at',)

# DeliveryTracking Admin
@admin.register(DeliveryTracking)
class DeliveryTrackingAdmin(admin.ModelAdmin):
    list_display = ('order', 'rider_latitude', 'rider_longitude', 'distance_to_delivery', 'estimated_time_remaining', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('order__id',)


# PlatformSettings Admin
@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ('default_commission_percentage', 'rider_commission_percentage', 'is_commission_active', 'delivery_percentage_off', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at',)
    
    fieldsets = (
        ('Commission & Discount Settings', {
            'fields': (
                'default_commission_percentage',
                'is_commission_active',
                'delivery_percentage_off',
                'rider_commission_percentage',
            )
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not PlatformSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)



@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'fixed_fee', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(EstateGatePass)
class EstateGatePassAdmin(admin.ModelAdmin):
    list_display = ('name', 'gate_fee_bike', 'gate_fee_bus', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


# PromoCode Admin
@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'promo_type', 'value', 'is_active', 'is_automatic', 'start_date', 'end_date', 'total_usage_limit')
    list_filter = ('promo_type', 'is_active', 'is_automatic')
    search_fields = ('code', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    filter_horizontal = ('applicable_zones', 'applicable_vendors', 'applicable_categories', 'applicable_customers')
    date_hierarchy = 'start_date'

    fieldsets = (
        ('Code & Type', {
            'fields': ('id', 'code', 'description', 'promo_type', 'value', 'is_automatic')
        }),
        ('Referral & New User', {
            'fields': ('is_new_user_promo', 'referrer_reward_type', 'referrer_reward_value'),
            'description': 'Configure how this promo interacts with referrals and new users.'
        }),
        ('Conditions', {
            'fields': ('min_order_value', 'max_discount', 'max_distance_km', 'usage_limit_per_user', 'total_usage_limit')
        }),
        ('Targets', {
            'fields': ('applicable_zones', 'applicable_vendors', 'applicable_categories', 'applicable_customers'),
            'classes': ('collapse',)
        }),
        ('Scheduling & Status', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# PromoUsage Admin
@admin.register(PromoUsage)
class PromoUsageAdmin(admin.ModelAdmin):
    list_display = ('promo', 'user', 'order', 'discount_amount', 'used_at')
    list_filter = ('promo__promo_type',)
    search_fields = ('promo__code', 'user__username', 'order__id')
    readonly_fields = ('used_at', 'promo', 'user', 'order', 'discount_amount', 'original_amount', 'final_amount', 'distance_at_usage')
    date_hierarchy = 'used_at'