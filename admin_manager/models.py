from django.db import models
from django.contrib.auth import get_user_model
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
