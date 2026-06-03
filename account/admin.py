from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    FCMToken, PushNotificationLog, ProductCreationGrant, User, Profile, Address, Vendor, VendorRating, Rider, RiderRating,
    VerificationCode, Notification, StaffPagePermission, StaffMarketplaceAssignment
)
from .models import Guarantor, Address
from product.models import BukaItemServiceCharge, Product, ServiceChargeTier

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    actions = ["set_delivery_percentage_off_for_selected", "send_bulk_notification_to_selected"]

    def send_bulk_notification_to_selected(self, request, queryset):
        from django import forms
        from django.shortcuts import render
        from django.contrib import messages
        from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
        from helpers.push_notification import notification_helper
        from .models import Notification

        class BulkNotificationForm(forms.Form):
            _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
            title = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'style': 'width: 100%;'}))
            body = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'style': 'width: 100%;'}), required=True)
            image_url = forms.URLField(required=False, widget=forms.TextInput(attrs={'style': 'width: 100%;'}), help_text="Optional image URL")

        if 'apply' in request.POST:
            form = BulkNotificationForm(request.POST)
            if form.is_valid():
                title = form.cleaned_data['title']
                body = form.cleaned_data['body']
                image_url = form.cleaned_data['image_url']
                selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
                
                users = User.objects.filter(pk__in=selected_ids, is_active=True)
                users_list = list(users)
                
                if not users_list:
                    self.message_user(request, "No active users selected.", messages.WARNING)
                    return None

                # 1. Create in-app notifications
                app_notifications = [
                    Notification(user=u, title=title, content=body)
                    for u in users_list
                ]
                Notification.objects.bulk_create(app_notifications)

                # 2. Send push notifications asynchronously
                notification_helper.send_to_users_with_executor(
                    users=users_list,
                    title=title,
                    body=body,
                    image_url=image_url if image_url else None
                )

                self.message_user(request, f"Bulk notification process initiated for {len(users_list)} users.")
                return None
        else:
            form = BulkNotificationForm(initial={
                '_selected_action': request.POST.getlist(ACTION_CHECKBOX_NAME)
            })

        return render(request, 'admin/send_bulk_notification_to_selected.html', {
            'users': queryset,
            'form': form,
            'title': 'Send Bulk Push Notification',
        })

    send_bulk_notification_to_selected.short_description = "Send bulk push notification to selected users"

    def set_delivery_percentage_off_for_selected(self, request, queryset):
        from django import forms
        from django.shortcuts import render
        from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
        class DeliveryOffForm(forms.Form):
            _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
            percentage = forms.DecimalField(label="Set Delivery Percentage Off (%)", min_value=0, max_value=100, decimal_places=2)

        if 'apply' in request.POST:
            form = DeliveryOffForm(request.POST)
            if form.is_valid():
                percentage = form.cleaned_data['percentage']
                # Get selected users from POST, not queryset (queryset is empty on POST)
                selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
                users = User.objects.filter(pk__in=selected_ids)
                
                count = 0
                for user in users:
                    if user.delivery_percentage_off != percentage:
                        user.delivery_percentage_off = percentage
                        user.save()  # This might not trigger save_model if called directly on model, but we can call our helper manually or rely on signals if we had them.
                        # Since save_model is ensuring notifications on save via admin form, but here we are doing manual save.
                        # We should call the notification helper directly.
                        self.send_delivery_discount_notification(user)
                        count += 1
                        
                self.message_user(request, f"Updated delivery percentage off to {percentage}% for {count} users.")
                return None
        else:
            form = DeliveryOffForm(initial={'_selected_action': request.POST.getlist(ACTION_CHECKBOX_NAME)})
        return render(request, 'admin/set_delivery_percentage_off.html', {
            'users': queryset,
            'form': form,
            'title': 'Set Delivery Percentage Off for Selected Users',
        })
    
    set_delivery_percentage_off_for_selected.short_description = "Set delivery percentage off for selected users"
    ordering = ['email']
    list_display = ('email', 'full_name', 'role', 'referral_code', 'is_active', 'is_staff', 'is_verified')
    list_filter = ('is_active', 'is_staff', 'role', 'is_verified')
    search_fields = ('email', 'full_name', 'phone_number', 'referral_code')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'first_name', 'last_name', 'phone_number', 'profile_image_url', 'delivery_percentage_off')}),
        ('Referral Info', {'fields': ('referral_code', 'referred_by')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_admin', 'role', 'is_verified')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
        ('Groups & Permissions', {'fields': ('groups', 'user_permissions')}),
    )

    def send_delivery_discount_notification(self, user):
        import logging
        from .models import Notification, PushNotificationLog
        from django.core.mail import send_mail
        
        logger = logging.getLogger("account.admin")
        
        # In-app notification
        Notification.objects.create(
            user=user,
            title="Delivery Discount Updated",
            content=f"Your delivery discount is now {user.delivery_percentage_off}% off."
        )
        logger.info(f"In-app notification sent to user {user.email} for delivery_percentage_off change.")
        
        # Push notification (log, actual push logic should be handled by a signal or async task)
        PushNotificationLog.objects.create(
            user=user,
            title="Delivery Discount Updated",
            body=f"Your delivery discount is now {user.delivery_percentage_off}% off.",
            status="sent"
        )
        logger.info(f"Push notification log created for user {user.email} for delivery_percentage_off change.")
        
        # Email notification
        try:
            send_mail(
                subject="Delivery Discount Updated",
                message=f"Hello {user.get_full_name() or user.email}, your delivery discount is now {user.delivery_percentage_off}% off.",
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True
            )
            logger.info(f"Email notification sent to user {user.email} for delivery_percentage_off change.")
        except Exception as e:
            logger.error(f"Failed to send email notification to user {user.email}: {e}")

    def save_model(self, request, obj, form, change):
        # Check if delivery_percentage_off changed
        if change:
            old_obj = type(obj).objects.get(pk=obj.pk)
            if old_obj.delivery_percentage_off != obj.delivery_percentage_off:
                self.send_delivery_discount_notification(obj)
        super().save_model(request, obj, form, change)

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


class VendorServiceChargeTierInline(admin.TabularInline):
    model = ServiceChargeTier
    extra = 1
    fields = ('system_category', 'min_price', 'max_price', 'flat_charge', 'is_active')
    autocomplete_fields = ('system_category',)
    show_change_link = True


class BukaItemServiceChargeInlineForm(forms.ModelForm):
    parent_vendor = None

    class Meta:
        model = BukaItemServiceCharge
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vendor_id = getattr(self.instance, 'vendor_id', None)
        if not vendor_id and self.parent_vendor:
            vendor_id = self.parent_vendor.id

        if vendor_id:
            self.fields['product'].queryset = Product.objects.filter(
                vendor_id=vendor_id,
                is_delete=False,
            ).order_by('name')
        else:
            self.fields['product'].queryset = Product.objects.none()


class BukaItemServiceChargeInline(admin.TabularInline):
    model = BukaItemServiceCharge
    form = BukaItemServiceChargeInlineForm
    extra = 1
    fields = ('product', 'flat_charge', 'is_active')
    show_change_link = True

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.parent_vendor = obj
        return formset


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'email', 'city', 'state',
        'is_active', 'is_featured', 'is_marketplace', 'approval_status',
        'rating', 'service_charge_tier_count', 'buka_item_charge_count', 'marketplace_delivery_fee',
    )
    list_filter = ('is_active', 'is_featured', 'is_marketplace', 'country', 'category', 'approval_status')
    search_fields = ('name', 'email', 'user__email', 'city', 'state')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [VendorServiceChargeTierInline, BukaItemServiceChargeInline]
    fieldsets = (
        ('Vendor Info', {
            'fields': ('user', 'name', 'email', 'phone_number', 'description',
                       'thumbnail_url', 'logo_url', 'category', 'is_marketplace'),
        }),
        ('Location', {
            'fields': ('country', 'state', 'city', 'address',
                       'location_latitude', 'location_longitude', 'delivery_radius_km'),
        }),
        ('Schedule', {
            'fields': ('open_day', 'close_day', 'open_time', 'close_time',
                       'estimated_delivery_time'),
        }),
        ('Financials', {
            'description': 'Service charge tiers for this vendor are managed in the inline rows below. marketplace_delivery_fee overrides the marketplace base fee for this vendor only.',
            'fields': ('marketplace_delivery_fee',
                       'starting_delivery_price',
                       'bank_account', 'bank_account_name', 'bank_name'),
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured', 'rating',
                       'approval_status', 'approval_comment'),
        }),
        ('Product creation lock', {
            'description': (
                "Vendors are auto-locked the first time admin pricing is set "
                "on one of their products if the category has "
                "lock_products_after_approval enabled. Grants let a locked "
                "vendor add N more products before re-locking."
            ),
            'fields': ('product_creation_locked', 'product_creation_grant_count'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Service charge tiers')
    def service_charge_tier_count(self, obj):
        return obj.service_charge_tiers.count()

    @admin.display(description='Buka item charges')
    def buka_item_charge_count(self, obj):
        return obj.buka_item_service_charges.count()

@admin.register(VendorRating)
class VendorRatingAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('vendor__name', 'user__email')
    readonly_fields = ('created_at',)


class GuarantorInline(admin.TabularInline):
    model = Guarantor
    extra = 0
    fields = ('name', 'phone_number', 'relationship', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = ('user', 'mode_of_transport', 'status', 'document_status', 'is_verified', 'is_online', 'is_in_house_rider', 'salary')
    list_filter = ('mode_of_transport', 'status', 'document_status', 'is_verified', 'is_online', 'is_in_house_rider')
    search_fields = ('user__email', 'vehicle_number')
    readonly_fields = ('created_at', 'updated_at', 'location_updated_at')
    inlines = [GuarantorInline]
    fieldsets = (
        (None, {'fields': ('user', 'mode_of_transport', 'vehicle_number', 'vehicle_brand', 'plate_number', 'status', 'document_status', 'is_verified', 'is_online', 'is_in_house_rider', 'salary')}),
        ('Verification Documents', {'fields': ('drivers_license_front', 'drivers_license_back', 'nin_front', 'nin_back', 'vehicle_insurance', 'vehicle_registration')}),
        ('Address', {'fields': ('country', 'state', 'city', 'address', 'location_latitude', 'location_longitude','preferred_location')}),
        ('Next of Kin', {'fields': ('next_of_kin', 'next_of_kin_phone')}),
        ('Performance', {'fields': ('on_time_delivery_rate', 'successful_delivery_rate', 'order_acceptance_rate', 'average_customer_rating')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'location_updated_at')}),
    )

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


@admin.register(FCMToken)
class FCMTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'device_id', 'is_active', 'created_at']
    list_filter = ['platform', 'is_active', 'created_at']
    search_fields = ['user__username', 'device_id']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(PushNotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at']

    
admin.site.register(RiderRating)


# ---------------------------------------------------------------------------
# Staff Page Permissions
# ---------------------------------------------------------------------------

class StaffPagePermissionInline(admin.TabularInline):
    model = StaffPagePermission
    fk_name = 'user'
    extra = 1
    fields = ('page',)
    readonly_fields = ()
    verbose_name = 'Page Access'
    verbose_name_plural = 'Custom Admin Page Access'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if not obj.pk:
                obj.granted_by = request.user
            obj.save()
        formset.save_m2m()


class StaffMarketplaceAssignmentInline(admin.TabularInline):
    model = StaffMarketplaceAssignment
    fk_name = 'user'
    extra = 2
    fields = ('marketplace',)
    autocomplete_fields = ('marketplace',)
    verbose_name = 'Marketplace Access'
    verbose_name_plural = 'Assigned Marketplaces'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'marketplace')

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if not obj.pk:
                obj.assigned_by = request.user
            obj.save()
        formset.save_m2m()


@admin.register(StaffPagePermission)
class StaffPagePermissionAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'user_full_name', 'page_display', 'granted_by_email', 'created_at')
    list_filter = ('page',)
    search_fields = ('user__email', 'user__full_name')
    readonly_fields = ('granted_by', 'created_at')
    autocomplete_fields = ('user',)

    fieldsets = (
        (None, {
            'fields': ('user', 'page'),
            'description': (
                'Grant a staff user access to a specific page in the custom admin dashboard. '
                'The user must have <strong>is_staff = True</strong> on their account.'
            ),
        }),
        ('Audit', {'fields': ('granted_by', 'created_at'), 'classes': ('collapse',)}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='User email', ordering='user__email')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Full name', ordering='user__full_name')
    def user_full_name(self, obj):
        return obj.user.full_name or '—'

    @admin.display(description='Page', ordering='page')
    def page_display(self, obj):
        return obj.get_page_display()

    @admin.display(description='Granted by', ordering='granted_by__email')
    def granted_by_email(self, obj):
        return obj.granted_by.email if obj.granted_by else '—'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'granted_by')


@admin.register(StaffMarketplaceAssignment)
class StaffMarketplaceAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'user_full_name', 'marketplace_name', 'assigned_by_email', 'created_at')
    list_filter = ('marketplace',)
    search_fields = ('user__email', 'user__full_name', 'marketplace__name')
    readonly_fields = ('assigned_by', 'created_at', 'updated_at')
    autocomplete_fields = ('user', 'marketplace')

    fieldsets = (
        (None, {
            'fields': ('user', 'marketplace'),
            'description': (
                'Assign marketplace staff to one or more marketplaces. '
                'Grant the same user the <strong>Marketplace Staff (limited)</strong> '
                'page permission for the dedicated pickup-confirmation page.'
            ),
        }),
        ('Audit', {'fields': ('assigned_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='User email', ordering='user__email')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Full name', ordering='user__full_name')
    def user_full_name(self, obj):
        return obj.user.full_name or '—'

    @admin.display(description='Marketplace', ordering='marketplace__name')
    def marketplace_name(self, obj):
        return obj.marketplace.name

    @admin.display(description='Assigned by', ordering='assigned_by__email')
    def assigned_by_email(self, obj):
        return obj.assigned_by.email if obj.assigned_by else '—'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'marketplace', 'assigned_by')


# ---------------------------------------------------------------------------
# Extend UserAdmin with page-permission inline + promote-to-staff action
# ---------------------------------------------------------------------------

# Unregister the existing UserAdmin and re-register with the inline
admin.site.unregister(User)


@admin.register(User)
class UserAdminWithPermissions(UserAdmin):
    inlines = [StaffPagePermissionInline, StaffMarketplaceAssignmentInline]
    actions = [
        'set_delivery_percentage_off_for_selected',
        'send_bulk_notification_to_selected',
        'promote_to_staff',
        'demote_from_staff',
        'grant_all_pages',
        'revoke_all_pages',
    ]

    def promote_to_staff(self, request, queryset):
        updated = queryset.filter(is_staff=False).update(is_staff=True)
        self.message_user(request, f"{updated} user(s) promoted to staff.")

    promote_to_staff.short_description = "Promote to staff (enable custom admin login)"

    def demote_from_staff(self, request, queryset):
        updated = queryset.exclude(is_superuser=True).filter(is_staff=True).update(is_staff=False)
        self.message_user(request, f"{updated} user(s) removed from staff.")

    demote_from_staff.short_description = "Remove staff status (disable custom admin login)"

    def grant_all_pages(self, request, queryset):
        pages = [p[0] for p in StaffPagePermission.PAGE_CHOICES]
        created = 0
        for user in queryset.filter(is_staff=True):
            for page in pages:
                _, is_new = StaffPagePermission.objects.get_or_create(
                    user=user, page=page, defaults={'granted_by': request.user}
                )
                if is_new:
                    created += 1
        self.message_user(request, f"Granted {created} new page permission(s).")

    grant_all_pages.short_description = "Grant ALL page access to selected staff users"

    def revoke_all_pages(self, request, queryset):
        deleted, _ = StaffPagePermission.objects.filter(user__in=queryset).delete()
        self.message_user(request, f"Revoked {deleted} page permission(s).")

    revoke_all_pages.short_description = "Revoke ALL page access from selected staff users"


@admin.register(ProductCreationGrant)
class ProductCreationGrantAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'action', 'count', 'balance_after', 'granted_by', 'created_at')
    list_filter = ('action',)
    search_fields = ('vendor__name', 'vendor__email', 'granted_by__email', 'note')
    readonly_fields = ('vendor', 'action', 'count', 'balance_after', 'granted_by', 'note', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
