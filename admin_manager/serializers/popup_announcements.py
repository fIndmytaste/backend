from rest_framework import serializers
from admin_manager.models import PopupAnnouncement, PopupAnnouncementView
from account.serializers import UserSerializer


class PopupAnnouncementSerializer(serializers.ModelSerializer):
    """
    Serializer for PopupAnnouncement model.
    """
    created_by_details = UserSerializer(source='created_by', read_only=True)
    is_viewed = serializers.SerializerMethodField()
    is_currently_active = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = PopupAnnouncement
        fields = [
            'id', 'title', 'message', 'image_file', 'image_url', 'image',
            'action_label', 'action_url', 'target_audience', 'start_date',
            'end_date', 'is_active', 'is_published', 'show_once_per_user',
            'created_by', 'created_by_details', 'created_at', 'updated_at',
            'view_count', 'click_count', 'is_viewed', 'is_currently_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'view_count', 'click_count']

    def get_is_viewed(self, obj):
        """Check if current user has viewed this popup"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return PopupAnnouncementView.objects.filter(
                popup=obj,
                user=request.user
            ).exists()
        return False

    def get_is_currently_active(self, obj):
        """Check if popup is currently active"""
        return obj.is_currently_active()

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image_file:
            url = obj.image_file.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        elif obj.image_url:
            return obj.image_url
        return None


class PopupAnnouncementCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating popup announcements.
    """
    class Meta:
        model = PopupAnnouncement
        fields = [
            'title', 'message', 'image_file', 'image_url', 'action_label',
            'action_url', 'target_audience', 'start_date', 'end_date',
            'is_active', 'is_published', 'show_once_per_user'
        ]

    def validate(self, data):
        """Validate dates"""
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] <= data['start_date']:
                raise serializers.ValidationError("End date must be after start date")
        return data


class PopupAnnouncementViewSerializer(serializers.ModelSerializer):
    """
    Serializer for tracking popup views.
    """
    popup_details = PopupAnnouncementSerializer(source='popup', read_only=True)
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = PopupAnnouncementView
        fields = ['id', 'popup', 'popup_details', 'user', 'user_details', 'viewed_at']
        read_only_fields = ['id', 'viewed_at']
