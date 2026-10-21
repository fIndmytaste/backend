from django.contrib import admin

from .models import Announcement, AnnouncementImage, AnnouncementLink, PopupAnnouncement, PopupAnnouncementView

class AnnouncementImageInline(admin.StackedInline):
    model = AnnouncementImage
    extra = 0
    max_num = 1
    can_delete = True
    fields = ('image_file', 'image_url', 'uploaded_at')
    readonly_fields = ('uploaded_at',)
    show_change_link = True

class AnnouncementLinkInline(admin.StackedInline):
    model = AnnouncementLink
    extra = 0
    max_num = 1
    can_delete = True
    fields = ('url', 'label', 'added_at')
    readonly_fields = ('added_at',)
    show_change_link = True


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'target_audience', 'priority', 'is_active', 
        'is_published', 'start_date', 'end_date', 'view_count', 'created_at'
    ]
    list_filter = ['target_audience', 'priority', 'is_active', 'is_published', 'created_at']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'updated_at', 'view_count']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'message', 'target_audience', 'priority')
        }),
        ('Scheduling', {
            'fields': ('start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('is_active', 'is_published', 'send_push_notification')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'view_count'),
            'classes': ('collapse',)
        }),
    )

    inlines = [AnnouncementImageInline, AnnouncementLinkInline]


@admin.register(PopupAnnouncement)
class PopupAnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_audience', 'is_active', 'is_published', 'show_once_per_user', 'start_date', 'end_date', 'view_count', 'created_at']
    list_filter = ['target_audience', 'is_active', 'is_published', 'show_once_per_user']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'updated_at', 'view_count', 'click_count']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Content', {
            'fields': ('title', 'message', 'image_file', 'image_url', 'action_url', 'action_label')
        }),
        ('Targeting & Display', {
            'fields': ('target_audience', 'show_once_per_user')
        }),
        ('Scheduling & Status', {
            'fields': ('start_date', 'end_date', 'is_active', 'is_published')
        }),
        ('Analytics', {
            'fields': ('view_count', 'click_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


from admin_manager.models import (  # noqa: E402
    AppVersionPolicy,
    EmailCampaign,
    RiderRewardAward,
    RiderRewardProgram,
    SupportSettings,
)


@admin.register(AppVersionPolicy)
class AppVersionPolicyAdmin(admin.ModelAdmin):
    list_display = ('app', 'platform', 'latest_version', 'minimum_version', 'is_active', 'updated_at')
    list_filter = ('app', 'platform', 'is_active')


@admin.register(SupportSettings)
class SupportSettingsAdmin(admin.ModelAdmin):
    list_display = ('whatsapp_number', 'whatsapp_enabled', 'live_chat_enabled', 'support_email', 'updated_at')


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'audience', 'status', 'recipient_count', 'sent_count', 'failed_count', 'sent_at')
    list_filter = ('status', 'audience')
    search_fields = ('subject',)
    readonly_fields = ('status', 'recipient_count', 'sent_count', 'failed_count', 'last_error', 'sent_at')


@admin.register(RiderRewardProgram)
class RiderRewardProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'target_deliveries', 'bonus_amount', 'period', 'is_active')
    list_filter = ('is_active', 'period')


@admin.register(RiderRewardAward)
class RiderRewardAwardAdmin(admin.ModelAdmin):
    list_display = ('program', 'rider', 'period_start', 'period_end', 'deliveries_counted', 'amount', 'created_at')
    list_filter = ('program',)
    readonly_fields = ('program', 'rider', 'period_start', 'period_end', 'deliveries_counted', 'amount', 'wallet_transaction')
