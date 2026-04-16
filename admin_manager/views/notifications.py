from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from admin_manager.serializers.notifications import BulkPushNotificationSerializer
from helpers.push_notification import notification_helper
from helpers.response.response_format import success_response, bad_request_response
from account.models import Notification
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class AdminBulkPushNotificationView(generics.GenericAPIView):
    """
    Admin view to send bulk push notifications to users.
    """
    permission_classes = [IsAdminUser]
    serializer_class = BulkPushNotificationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        target_type = serializer.validated_data['target_type']
        title = serializer.validated_data['title']
        body = serializer.validated_data['body']
        image_url = serializer.validated_data.get('image_url')
        data = serializer.validated_data.get('data', {})
        user_ids = serializer.validated_data.get('user_ids', [])

        # Determine target users
        queryset = User.objects.filter(is_active=True)
        
        if target_type == 'buyer':
            queryset = queryset.filter(role='buyer')
        elif target_type == 'vendor':
            queryset = queryset.filter(role='vendor')
        elif target_type == 'rider':
            queryset = queryset.filter(role='rider')
        elif target_type == 'specific':
            queryset = queryset.filter(id__in=user_ids)
        elif target_type == 'all':
            pass # No additional filtering needed
            
        users = list(queryset)
        
        if not users:
            return bad_request_response(
                message="No active users found for the selected target audience.",
                status_code=404
            )

        # Create in-app notifications in bulk for performance
        notifications = [
            Notification(
                user=user,
                title=title,
                content=body
            ) for user in users
        ]
        Notification.objects.bulk_create(notifications)

        # Send push notifications using the helper's executor for efficiency
        # The helper already handles PushNotificationLog creation via FirebaseNotificationService
        results = notification_helper.send_to_users_with_executor(
            users=users,
            title=title,
            body=body,
            data=data,
            image_url=image_url
        )

        return success_response(
            message=f"Bulk notification process initiated for {len(users)} users.",
            data={
                "total_users": len(users),
                "success_count": results.get('success_count', 0),
                "failure_count": results.get('failure_count', 0),
                "results": results.get('results', [])
            }
        )
