from rest_framework import serializers

class BulkPushNotificationSerializer(serializers.Serializer):
    """Serializer for sending bulk push notifications"""
    
    TARGET_CHOICES = [
        ('all', 'All Users'),
        ('buyer', 'Buyers/Customers'),
        ('vendor', 'Vendors'),
        ('rider', 'Riders'),
        ('specific', 'Specific Users'),
    ]
    
    title = serializers.CharField(max_length=255, required=True, help_text="Notification title")
    body = serializers.CharField(required=True, help_text="Notification body")
    target_type = serializers.ChoiceField(choices=TARGET_CHOICES, default='all', help_text="Who to send the notification to")
    user_ids = serializers.ListField(
        child=serializers.UUIDField(), 
        required=False, 
        help_text="List of User IDs (required if target_type is 'specific')"
    )
    image_url = serializers.URLField(required=False, allow_blank=True, help_text="Optional image URL")
    data = serializers.JSONField(required=False, default=dict, help_text="Optional extra data payload")
    
    def validate(self, data):
        """Validate that user_ids is provided if target_type is 'specific'"""
        if data.get('target_type') == 'specific' and not data.get('user_ids'):
            raise serializers.ValidationError({"user_ids": "This field is required when target_type is 'specific'"})
        return data
