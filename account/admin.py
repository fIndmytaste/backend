from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    FCMToken, PushNotificationLog, User, Profile, Address, Vendor, VendorRating, Rider, RiderRating,
    VerificationCode, Notification
)
# ...existing code...
from .models import Guarantor, Address

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

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'user', 'email', 'phone_number',
        'country', 'state', 'city', 'address', 'location_latitude', 'location_longitude',
        'is_active', 'is_featured', 'rating', 'commission_percentage', 'approval_status'
    )
    list_filter = ('is_active', 'is_featured', 'country', 'category', 'approval_status')
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


class GuarantorInline(admin.TabularInline):
    model = Guarantor
    extra = 0
    fields = ('name', 'phone_number', 'relationship', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = ('user', 'mode_of_transport', 'status', 'document_status', 'is_verified', 'is_online')
    list_filter = ('mode_of_transport', 'status', 'document_status', 'is_verified', 'is_online')
    search_fields = ('user__email', 'vehicle_number')
    readonly_fields = ('created_at', 'updated_at', 'location_updated_at')
    inlines = [GuarantorInline]
    fieldsets = (
        (None, {'fields': ('user', 'mode_of_transport', 'vehicle_number', 'vehicle_brand', 'plate_number', 'status', 'document_status', 'is_verified', 'is_online', 'is_in_house_rider', 'salary')}),
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
