from django.contrib import admin

from vendor.models import MarketPlace


@admin.register(MarketPlace)
class MarketPlaceAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'is_active',
        'delivery_fee', 'second_item_fee', 'additional_item_fee',
        'special_category_discount_percentage', 'has_perishables',
        'vendor_count', 'updated_at',
    )
    list_editable = ('is_active', 'delivery_fee', 'second_item_fee', 'additional_item_fee')
    list_filter = ('is_active', 'has_perishables')
    search_fields = ('name',)
    filter_horizontal = ('vendors',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'description', 'is_active', 'has_perishables'),
        }),
        ('Delivery Pricing', {
            'description': (
                'Standard pricing: item 1 = delivery_fee, item 2 = delivery_fee + second_item_fee, '
                'item 3+ = base_for_two + (additional_item_fee × extra items). '
                'Special pricing (is_special_pricing on category): first item full price, '
                'remaining items at (delivery_fee × (1 - special_category_discount_percentage/100)).'
            ),
            'fields': (
                'delivery_fee', 'second_item_fee', 'additional_item_fee',
                'special_category_discount_percentage',
            ),
        }),
        ('Vendors', {
            'fields': ('vendors',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def vendor_count(self, obj):
        return obj.vendors.count()
    vendor_count.short_description = 'Vendors'