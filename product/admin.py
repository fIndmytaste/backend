# from django.contrib import admin
# from .models import SystemCategory, VendorCategory, Product, ProductImage, Order,OrderItem,Rating,Favorite,ProductView
# # Register your models here.


# admin.site.register(SystemCategory)
# admin.site.register(VendorCategory)
# admin.site.register(Product)
# admin.site.register(ProductImage)
# admin.site.register(Order)
# admin.site.register(OrderItem)
# admin.site.register(Rating)
# admin.site.register(Favorite)
# admin.site.register(ProductView)

from django.contrib import admin
from .models import (
    SystemCategory, VendorCategory, Product, ProductImage,
    Order, OrderItem, Rating, Favorite, ProductView, DeliveryTracking
)

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
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    ordering = ('-created_at',)

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
@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__username', 'product__name')
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
