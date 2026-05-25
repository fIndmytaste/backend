from django.contrib import admin
from django import forms
from django.http import JsonResponse
from django.urls import path, reverse
from .models import (
    SystemCategory, VendorCategory, Product, ProductImage,
    Order, OrderItem, Rating, UserFavoriteVendor, ProductView, DeliveryTracking,
    PlatformSettings, DeliveryZone, EstateGatePass,
    ServiceChargeTier, BukaItemServiceCharge, BukaVariantServiceCharge, ProductVariant,
)
from .promo_models import PromoCode, PromoUsage

class BukaItemServiceChargeForm(forms.ModelForm):
    class Meta:
        model = BukaItemServiceCharge
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vendor_id = (
            self.data.get('vendor')
            or self.initial.get('vendor')
            or getattr(self.instance, 'vendor_id', None)
        )

        if vendor_id:
            self.fields['product'].queryset = Product.objects.filter(
                vendor_id=vendor_id,
                is_delete=False,
            ).order_by('name')
        else:
            self.fields['product'].queryset = Product.objects.none()
            self.fields['product'].help_text = 'Choose a vendor first, then select one of that vendor’s products.'

        self.fields['product'].widget.attrs['data-current-product'] = str(
            getattr(self.instance, 'product_id', '') or ''
        )


class BukaVariantServiceChargeForm(forms.ModelForm):
    class Meta:
        model = BukaVariantServiceCharge
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vendor_id = (
            self.data.get('vendor')
            or self.initial.get('vendor')
            or getattr(self.instance, 'vendor_id', None)
        )
        product_id = (
            self.data.get('product')
            or self.initial.get('product')
            or getattr(self.instance, 'product_id', None)
        )

        if vendor_id:
            self.fields['product'].queryset = Product.objects.filter(
                vendor_id=vendor_id,
                is_delete=False,
            ).order_by('name')
        else:
            self.fields['product'].queryset = Product.objects.none()
            self.fields['product'].help_text = 'Choose a vendor first, then select one of that vendor’s products.'

        if product_id:
            self.fields['variant'].queryset = ProductVariant.objects.filter(
                product_id=product_id,
                is_active=True,
            ).select_related('category').order_by('category__category_name', 'name')
        else:
            self.fields['variant'].queryset = ProductVariant.objects.none()
            self.fields['variant'].help_text = 'Choose a product first, then select one of its variants.'


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
    list_display = ('name', 'fixed_fee', 'second_item_fee', 'additional_item_fee', 'is_active', 'created_at')
    list_editable = ('fixed_fee', 'second_item_fee', 'additional_item_fee', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name', 'boundary', 'is_active'),
        }),
        ('Delivery Pricing', {
            'description': (
                'Zone pricing: item 1 = fixed_fee, item 2 = fixed_fee + second_item_fee, '
                'item 3+ = base_for_two + (additional_item_fee × extra items).'
            ),
            'fields': ('fixed_fee', 'second_item_fee', 'additional_item_fee'),
        }),
    )

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
        ('Where this promo can be used (optional)', {
            'fields': ('applicable_zones', 'applicable_vendors', 'applicable_categories', 'applicable_customers'),
            'description': 'Leave these blank for the promo to work everywhere. Select vendors, system categories, zones, or customers here to restrict where the code can be used.'
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


@admin.register(ServiceChargeTier)
class ServiceChargeTierAdmin(admin.ModelAdmin):
    list_display = ('system_category', 'vendor', 'min_price', 'max_price', 'flat_charge', 'is_active', 'updated_at')
    list_display_links = ('system_category',)
    list_editable = ('min_price', 'max_price', 'flat_charge', 'is_active')
    list_filter = ('system_category', 'vendor', 'is_active')
    search_fields = ('system_category__name', 'vendor__name', 'vendor__email')
    ordering = ('system_category__name', 'vendor__name', 'min_price')
    fieldsets = (
        (None, {
            'fields': ('system_category', 'vendor', 'is_active'),
            'description': 'Choose a vendor to make this tier apply only to that vendor. Leave Vendor blank for the category default.',
        }),
        ('Price Range', {
            'description': 'Set the product price range this flat charge applies to. Leave Max Price blank for an open-ended top tier.',
            'fields': ('min_price', 'max_price'),
        }),
        ('Service Charge', {
            'description': 'Fixed naira amount added to the product price. Editable at any time without app update.',
            'fields': ('flat_charge',),
        }),
    )


@admin.register(BukaItemServiceCharge)
class BukaItemServiceChargeAdmin(admin.ModelAdmin):
    form = BukaItemServiceChargeForm
    list_display = ('vendor', 'product', 'flat_charge', 'is_active', 'updated_at')
    list_display_links = ('product',)
    list_editable = ('flat_charge', 'is_active')
    list_filter = ('vendor', 'is_active')
    search_fields = ('product__name', 'product__vendor__name', 'product__vendor__email')
    fieldsets = (
        (None, {
            'fields': ('vendor', 'product', 'is_active'),
            'description': 'Choose the vendor first. The Product field will then show only that vendor’s products.',
        }),
        ('Service Charge', {
            'description': 'Fixed naira amount added per unit. Formula: (Base Price + Charge) × Quantity.',
            'fields': ('flat_charge',),
        }),
    )

    class Media:
        js = ('admin/js/buka_service_charge_product_filter.js',)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        form.base_fields['product'].widget.attrs['data-vendor-products-url'] = reverse(
            'admin:product_bukaitemservicecharge_vendor_products'
        )
        return form

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'vendor-products/',
                self.admin_site.admin_view(self.vendor_products_view),
                name='product_bukaitemservicecharge_vendor_products',
            ),
        ]
        return custom_urls + urls

    def vendor_products_view(self, request):
        vendor_id = request.GET.get('vendor')
        products = Product.objects.none()
        if vendor_id:
            products = Product.objects.filter(
                vendor_id=vendor_id,
                is_delete=False,
            ).order_by('name')

        return JsonResponse({
            'products': [
                {
                    'id': str(product.id),
                    'name': product.name,
                    'price': float(product.price),
                }
                for product in products
            ]
        })

    @admin.display(description='Vendor')
    def vendor_name(self, obj):
        return obj.vendor.name if obj.vendor else '—'


@admin.register(BukaVariantServiceCharge)
class BukaVariantServiceChargeAdmin(admin.ModelAdmin):
    form = BukaVariantServiceChargeForm
    list_display = ('vendor', 'product', 'variant', 'flat_charge', 'is_active', 'updated_at')
    list_display_links = ('variant',)
    list_editable = ('flat_charge', 'is_active')
    list_filter = ('vendor', 'is_active')
    search_fields = ('product__name', 'variant__name', 'vendor__name', 'vendor__email')
    fieldsets = (
        (None, {
            'fields': ('vendor', 'product', 'variant', 'is_active'),
            'description': 'Choose the vendor, then the product, then the product variant.',
        }),
        ('Service Charge', {
            'description': 'Fixed naira amount added per selected variant.',
            'fields': ('flat_charge',),
        }),
    )
