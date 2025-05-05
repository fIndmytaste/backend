# from django.contrib import admin
# from .models import User, Rider, Vendor, VendorRating,VerificationCode, Profile, Notification
# # Register your models here.


# admin.site.register(User)
# admin.site.register(Rider)
# admin.site.register(Vendor)
# admin.site.register(VendorRating)
# admin.site.register(VerificationCode)
# admin.site.register(Profile) 
# admin.site.register(Notification)


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Profile, Address, Vendor, VendorRating, Rider,
    VerificationCode, Notification
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    list_display = ('email', 'full_name', 'role', 'is_active', 'is_staff', 'is_verified')
    list_filter = ('is_active', 'is_staff', 'role', 'is_verified')
    search_fields = ('email', 'full_name', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'first_name', 'last_name', 'phone_number', 'profile_image')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_admin', 'role', 'is_verified')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
        ('Groups & Permissions', {'fields': ('groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role'),
        }),
    )

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'country', 'state', 'city', 'is_primary', 'is_active')
    list_filter = ('is_primary', 'is_active', 'country')
    search_fields = ('user__email', 'city', 'state', 'country')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'email', 'phone_number', 'is_active', 'is_featured', 'rating')
    list_filter = ('is_active', 'is_featured', 'country', 'category')
    search_fields = ('name', 'email', 'user__email', 'city', 'state')
    readonly_fields = ('created_at', 'updated_at')
    # fieldsets = (
    #     ('Vendor Info', {
    #         'fields': ('user', 'name', 'email', 'phone_number', 'description', 'thumbnail', 'logo', 'category')
    #     }),
    #     ('Location', {
    #         'fields': ('country', 'state', 'city', 'address', 'location_latitude', 'location_longitude')
    #     }),
    #     ('Bank Details', {
    #         'fields': ('bank_account', 'bank_account_name', 'bank_name')
    #     }),
    #     ('Schedule', {
    #         'fields': ('open_day', 'close_day', 'open_time', 'close_time')
    #     }),
    #     ('Status', {
    #         'fields': ('is_active', 'is_featured', 'rating')
    #     }),
    #     ('Timestamps', {
    #         'fields': ('created_at', 'updated_at')
    #     }),
    # )

@admin.register(VendorRating)
class VendorRatingAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('vendor__name', 'user__email')
    readonly_fields = ('created_at',)

@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = ('user', 'mode_of_transport', 'status', 'is_verified', 'is_online')
    list_filter = ('mode_of_transport', 'status', 'is_verified', 'is_online')
    search_fields = ('user__email', 'vehicle_number')
    readonly_fields = ('created_at', 'updated_at', 'location_updated_at')

@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'verification_type', 'is_active', 'created_at')
    list_filter = ('verification_type', 'is_active')
    search_fields = ('user__email', 'code')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'read', 'created_at')
    list_filter = ('read',)
    search_fields = ('user__email', 'title')
    readonly_fields = ('created_at', 'updated_at')
