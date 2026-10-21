from django.db import models
from django.contrib.auth import get_user_model
import os
import uuid

User = get_user_model()


class Announcement(models.Model):
    """
    Model for system-wide announcements to riders, customers, and vendors.
    """
    
    TARGET_AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('customer', 'Customers'),
        ('vendor', 'Vendors'),
        ('rider', 'Riders'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, help_text="Announcement title")
    message = models.TextField(help_text="Announcement message/content")
    target_audience = models.CharField(
        max_length=20, 
        choices=TARGET_AUDIENCE_CHOICES, 
        default='all',
        help_text="Target audience for this announcement"
    )
    priority = models.CharField(
        max_length=20, 
        choices=PRIORITY_CHOICES, 
        default='medium',
        help_text="Priority level of the announcement"
    )
    
    # Removed single image and link fields; see AnnouncementImage and AnnouncementLink below
    
    # Scheduling
    start_date = models.DateTimeField(help_text="When the announcement becomes active")
    end_date = models.DateTimeField(blank=True, null=True, help_text="When the announcement expires (optional)")
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Whether the announcement is currently active")
    is_published = models.BooleanField(default=False, help_text="Whether the announcement is published")
    send_push_notification = models.BooleanField(default=False, help_text="Send push notification to users")
    
    # Metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_announcements',
        help_text="Admin user who created this announcement"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analytics
    view_count = models.IntegerField(default=0, help_text="Number of times viewed")
    
    class Meta:
        db_table = 'announcements'
        ordering = ['-priority', '-created_at']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        indexes = [
            models.Index(fields=['target_audience', 'is_active', 'is_published']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.target_audience}"
    
    def increment_view_count(self):
        """Increment the view count for this announcement."""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def is_currently_active(self):
        """Check if the announcement is currently active based on dates."""
        from django.utils import timezone
        now = timezone.now()
        
        if not self.is_active or not self.is_published:
            return False
        
        if self.start_date > now:
            return False
        
        if self.end_date and self.end_date < now:
            return False
        
        return True


class AnnouncementImage(models.Model):
    """
    Store a single optional image for an announcement. Supports file upload or external URL.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.OneToOneField(
        Announcement,
        on_delete=models.CASCADE,
        related_name='image',
        null=True,
        blank=True,
    )
    image_file = models.ImageField(upload_to='announcement_images/', null=True, blank=True, help_text="Upload image file for the announcement.")
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Image URL for the announcement (optional if file is uploaded).")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'announcement_images'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Image for {self.announcement.title}"

    def save(self, *args, **kwargs):
        """Persist newly uploaded carousel images in the existing Backblaze bucket."""
        image = self.image_file
        if image and not getattr(image, '_committed', True):
            from helpers.backblaze import upload_to_backblaze

            extension = os.path.splitext(image.name)[1].lower()
            filename = f"announcement_{uuid.uuid4().hex}{extension}"
            result = upload_to_backblaze(
                image.file,
                filename,
                folder='announcement_images',
                content_type=getattr(image.file, 'content_type', None),
            )
            self.image_url = result['downloadUrl']
            # Store the durable Backblaze URL, not a Render-local ImageField
            # path. This also prevents Django's default storage from receiving
            # the same upload a second time.
            self.image_file = None

        super().save(*args, **kwargs)


class AnnouncementLink(models.Model):
    """
    Store a single optional link for an announcement (e.g., action or deep link).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.OneToOneField(
        Announcement,
        on_delete=models.CASCADE,
        related_name='link',
        null=True,
        blank=True,
    )
    url = models.URLField(max_length=500, help_text="Link URL for the announcement.")
    label = models.CharField(max_length=100, blank=True, null=True, help_text="Label for the link/action button.")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'announcement_links'
        ordering = ['added_at']

    def __str__(self):
        return f"Link for {self.announcement.title}: {self.label or self.url}"


# Track which users have viewed which announcements.
class AnnouncementView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(
        Announcement, 
        on_delete=models.CASCADE, 
        related_name='user_views'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='announcement_views'
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'announcement_views'
        unique_together = ['announcement', 'user']
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user.email} viewed {self.announcement.title}"

class PopupAnnouncement(models.Model):
    """
    Model for full-screen/modal announcements that appear when the app opens.
    """
    TARGET_AUDIENCE_CHOICES = Announcement.TARGET_AUDIENCE_CHOICES
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, help_text="Popup title")
    message = models.TextField(help_text="Popup message/content")
    
    # Media
    image_file = models.ImageField(upload_to='popup_images/', null=True, blank=True, help_text="Upload image file for the popup.")
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Image URL for the popup (optional if file is uploaded).")
    
    # Action
    action_label = models.CharField(max_length=100, blank=True, null=True, help_text="Label for the action button (e.g., 'Start Saving Now')")
    action_url = models.CharField(max_length=500, blank=True, null=True, help_text="URL or Deep Link for the action button")
    
    # Targeting & Scheduling
    target_audience = models.CharField(
        max_length=20, 
        choices=TARGET_AUDIENCE_CHOICES, 
        default='all',
        help_text="Target audience for this popup"
    )
    start_date = models.DateTimeField(help_text="When the popup becomes active")
    end_date = models.DateTimeField(blank=True, null=True, help_text="When the popup expires (optional)")
    
    # Display Logic
    is_active = models.BooleanField(default=True, help_text="Whether the popup is currently active")
    is_published = models.BooleanField(default=False, help_text="Whether the popup is published")
    show_once_per_user = models.BooleanField(default=True, help_text="Whether to show this popup only once per user")
    
    # Metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_popups',
        help_text="Admin user who created this popup"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analytics
    view_count = models.IntegerField(default=0, help_text="Number of times viewed")
    click_count = models.IntegerField(default=0, help_text="Number of times action button was clicked")

    class Meta:
        db_table = 'popup_announcements'
        ordering = ['-created_at']
        verbose_name = 'Popup Announcement'
        verbose_name_plural = 'Popup Announcements'
        indexes = [
            models.Index(fields=['target_audience', 'is_active', 'is_published']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"Popup: {self.title} - {self.target_audience}"

    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])

    def increment_click_count(self):
        self.click_count += 1
        self.save(update_fields=['click_count'])

    def is_currently_active(self):
        from django.utils import timezone
        now = timezone.now()
        
        if not self.is_active or not self.is_published:
            return False
        
        if self.start_date > now:
            return False
        
        if self.end_date and self.end_date < now:
            return False
        
        return True


class PopupAnnouncementView(models.Model):
    """
    Track which users have viewed which popup announcements.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    popup = models.ForeignKey(
        PopupAnnouncement, 
        on_delete=models.CASCADE, 
        related_name='user_views'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='popup_views'
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'popup_announcement_views'
        unique_together = ['popup', 'user']
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user.email} viewed popup {self.popup.title}"


# ─────────────────────────────────────────────────────────────────────────────
# App update policy
# ─────────────────────────────────────────────────────────────────────────────

class AppVersionPolicy(models.Model):
    """
    What version each app should be on, per platform.

    The apps call /app-version/check/ on launch with their own version. When
    it is below `minimum_version` the update is required and the app blocks
    until the user updates; when only below `latest_version` the app shows a
    dismissible "update available" prompt.
    """

    APP_CHOICES = [
        ('customer', 'Customer app'),
        ('vendor', 'Vendor app'),
        ('rider', 'Rider app'),
    ]
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app = models.CharField(max_length=16, choices=APP_CHOICES)
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    latest_version = models.CharField(
        max_length=32, help_text="Newest release in the store, e.g. 1.0.4")
    minimum_version = models.CharField(
        max_length=32, blank=True, default='',
        help_text="Versions below this must update before using the app. Blank = no forced update.")
    store_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text="Play Store / App Store link the update button opens.")
    release_notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='app_version_policies_updated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['app', 'platform'], name='unique_app_version_policy'),
        ]
        ordering = ['app', 'platform']

    def __str__(self):
        return f"{self.get_app_display()} ({self.get_platform_display()}): {self.latest_version}"


# ─────────────────────────────────────────────────────────────────────────────
# Support contact settings
# ─────────────────────────────────────────────────────────────────────────────

class SupportSettings(models.Model):
    """Singleton: how users can reach support from "Reach out to support"."""

    whatsapp_number = models.CharField(
        max_length=20, blank=True, default='',
        help_text="International format without +, e.g. 2348012345678.")
    whatsapp_message = models.CharField(
        max_length=255, blank=True, default='Hello Find My Taste support, I need help with',
        help_text="Text pre-filled in the WhatsApp chat.")
    whatsapp_enabled = models.BooleanField(default=True)
    live_chat_enabled = models.BooleanField(default=True)
    support_email = models.EmailField(blank=True, default='support@findmytaste.com.ng')
    support_phone = models.CharField(max_length=20, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Support settings'
        verbose_name_plural = 'Support settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Support settings'


# ─────────────────────────────────────────────────────────────────────────────
# Email campaigns
# ─────────────────────────────────────────────────────────────────────────────

class EmailCampaign(models.Model):
    """A promotional / update email the admin sends to a group of users."""

    AUDIENCE_CHOICES = [
        ('all', 'All users'),
        ('customers', 'Customers'),
        ('vendors', 'Vendors'),
        ('riders', 'Riders'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=200)
    preheader = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Preview line shown next to the subject in inboxes.")
    heading = models.CharField(max_length=200, blank=True, default='')
    body = models.TextField(help_text="Plain text. Blank lines start new paragraphs.")
    cta_label = models.CharField(max_length=60, blank=True, default='')
    cta_url = models.URLField(max_length=500, blank=True, default='')
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default='all')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft')

    recipient_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='email_campaigns')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} ({self.status})"

    def recipients(self):
        """Active, verified users in the audience who still accept marketing mail."""
        qs = User.objects.filter(
            is_active=True,
            marketing_emails_opt_in=True,
        ).exclude(email__isnull=True).exclude(email='')
        role = {'customers': 'buyer', 'vendors': 'vendor', 'riders': 'rider'}.get(self.audience)
        if role:
            qs = qs.filter(role=role)
        else:
            qs = qs.filter(role__in=['buyer', 'vendor', 'rider'])
        return qs


# ─────────────────────────────────────────────────────────────────────────────
# Rider rewards
# ─────────────────────────────────────────────────────────────────────────────

class RiderRewardProgram(models.Model):
    """
    A delivery target with a cash bonus, e.g. 10 deliveries in a week earns
    ₦2,000. The admin can switch a programme on and off at any time; only
    active programmes award bonuses.
    """

    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly (Mon–Sun)'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom dates'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    target_deliveries = models.PositiveIntegerField()
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2)
    period = models.CharField(max_length=16, choices=PERIOD_CHOICES, default='weekly')
    start_date = models.DateField(null=True, blank=True, help_text="Required for custom periods.")
    end_date = models.DateField(null=True, blank=True, help_text="Required for custom periods.")
    is_active = models.BooleanField(default=False)
    include_in_house_riders = models.BooleanField(
        default=False, help_text="Salaried marketplace riders are excluded unless ticked.")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rider_reward_programs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name}: {self.target_deliveries} deliveries → ₦{self.bonus_amount}"

    def current_window(self, today=None):
        """(start_date, end_date) of the period containing `today`, inclusive."""
        from datetime import timedelta
        from django.utils import timezone
        import calendar

        today = today or timezone.localdate()
        if self.period == 'daily':
            return today, today
        if self.period == 'weekly':
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=6)
        if self.period == 'monthly':
            last = calendar.monthrange(today.year, today.month)[1]
            return today.replace(day=1), today.replace(day=last)
        return self.start_date, self.end_date


class RiderRewardAward(models.Model):
    """One bonus paid to one rider for one programme window. Never paid twice."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        RiderRewardProgram, on_delete=models.CASCADE, related_name='awards')
    rider = models.ForeignKey(
        'account.Rider', on_delete=models.CASCADE, related_name='reward_awards')
    period_start = models.DateField()
    period_end = models.DateField()
    deliveries_counted = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    wallet_transaction = models.ForeignKey(
        'wallet.WalletTransaction', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rider_reward_awards')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['program', 'rider', 'period_start'],
                name='unique_rider_reward_per_period',
            ),
        ]

    def __str__(self):
        return f"{self.rider} earned ₦{self.amount} ({self.program.name})"
