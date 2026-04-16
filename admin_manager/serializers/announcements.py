from rest_framework import serializers
from admin_manager.models import Announcement, AnnouncementImage, AnnouncementLink, AnnouncementView
class AnnouncementImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementImage
        fields = ['id', 'image_url', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class AnnouncementLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementLink
        fields = ['id', 'url', 'label', 'added_at']
        read_only_fields = ['id', 'added_at']

from account.serializers import UserSerializer


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model"""

    created_by_details = UserSerializer(source='created_by', read_only=True)
    is_viewed = serializers.SerializerMethodField()
    is_currently_active = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'message', 'target_audience', 'priority',
            'start_date', 'end_date', 'is_active', 'is_published',
            'send_push_notification', 'created_by', 'created_by_details',
            'created_at', 'updated_at', 'view_count', 'is_viewed',
            'is_currently_active', 'image', 'link'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'view_count']

    def get_is_viewed(self, obj):
        """Check if current user has viewed this announcement"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return AnnouncementView.objects.filter(
                announcement=obj,
                user=request.user
            ).exists()
        return False

    def get_is_currently_active(self, obj):
        """Check if announcement is currently active"""
        return obj.is_currently_active()

    def get_image(self, obj: Announcement):
        image_obj = getattr(obj, 'image', None)
        request = self.context.get('request')
        if image_obj:
            if image_obj.image_file:
                url = image_obj.image_file.url
                if request is not None:
                    return request.build_absolute_uri(url) 
                return url
            elif image_obj.image_url:
                return image_obj.image_url
        return None

    def get_link(self, obj):
        if hasattr(obj, 'link') and obj.link:
            return obj.link.url
        return None


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating announcements"""
    
    class Meta:
        model = Announcement
        fields = [
            'title', 'message', 'target_audience', 'priority',
            'start_date', 'end_date', 'is_active', 'is_published',
            'send_push_notification'
        ]
    
    def validate(self, data):
        """Validate announcement data"""
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] <= data['start_date']:
                raise serializers.ValidationError(
                    "End date must be after start date"
                )
        return data


class AnnouncementViewSerializer(serializers.ModelSerializer):
    """Serializer for tracking announcement views"""
    
    announcement_details = AnnouncementSerializer(source='announcement', read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = AnnouncementView
        fields = ['id', 'announcement', 'announcement_details', 'user', 'user_details', 'viewed_at']
        read_only_fields = ['id', 'viewed_at']


class MarkAnnouncementViewedSerializer(serializers.Serializer):
    """Serializer for marking an announcement as viewed"""
    
    announcement_id = serializers.UUIDField()
