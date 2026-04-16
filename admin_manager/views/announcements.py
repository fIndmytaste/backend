from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from admin_manager.models import Announcement, AnnouncementView
from admin_manager.serializers import (
    AnnouncementSerializer,
    AnnouncementCreateSerializer,
    MarkAnnouncementViewedSerializer
)
from helpers.response.response_format import (
    success_response,
    bad_request_response,
    paginate_success_response_with_serializer
)
from helpers.push_notification import notification_helper


class AnnouncementListView(generics.ListAPIView):
    """
    Get list of announcements for the current user based on their role.
    Filters announcements by target audience and active status.
    """
    serializer_class = AnnouncementSerializer
    permission_classes = []
    
    def get_queryset(self):
        user = self.request.user
        user_role = self.request.GET.get('role', 'customer')  # default to customer if not authenticated
        now = timezone.now()
        
        # Determine user role
        # user_role = 'customer'  # default
        # if hasattr(user, 'role'):
        #     user_role = user.role
        
        # Build query to get announcements for this user
        queryset = Announcement.objects.filter(
            is_active=True,
            is_published=True,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).filter(
            Q(target_audience='all') | Q(target_audience=user_role)
        )
        
        # Filter by priority if specified
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        return queryset.order_by('-priority', '-created_at')
    
    @swagger_auto_schema(
        operation_summary="Get announcements for current user",
        operation_description="Retrieve all active announcements for the current user based on their role (customer, vendor, or rider).",
        manual_parameters=[
            openapi.Parameter(
                'priority',
                openapi.IN_QUERY,
                description="Filter by priority (low, medium, high, critical)",
                type=openapi.TYPE_STRING
            ),
        ],
        responses={
            200: AnnouncementSerializer(many=True),
            401: "Unauthorized"
        }
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            queryset,
            page_size=int(request.GET.get('page_size', 20))
        )


class AnnouncementDetailView(generics.RetrieveAPIView):
    """
    Get detailed information about a specific announcement.
    """
    serializer_class = AnnouncementSerializer
    permission_classes = []
    lookup_field = 'id'
    
    def get_queryset(self):
        user_role = self.request.GET.get('role', 'customer')
        
        return Announcement.objects.filter(
            Q(target_audience='all') | Q(target_audience=user_role)
        )
    
    @swagger_auto_schema(
        operation_summary="Get announcement details",
        operation_description="Retrieve detailed information about a specific announcement.",
        responses={
            200: AnnouncementSerializer(),
            404: "Announcement not found",
            401: "Unauthorized"
        }
    )
    def get(self, request, *args, **kwargs):
        try:
            announcement = self.get_object()
            
            # Increment view count
            announcement.increment_view_count()
            
            # Mark as viewed by this user
            AnnouncementView.objects.get_or_create(
                announcement=announcement,
                user=request.user
            )
            
            serializer = self.get_serializer(announcement)
            return success_response(data=serializer.data)
            
        except Announcement.DoesNotExist:
            return bad_request_response(
                message="Announcement not found",
                status_code=404
            )


class MarkAnnouncementAsViewedView(generics.GenericAPIView):
    """
    Mark an announcement as viewed by the current user.
    """
    serializer_class = MarkAnnouncementViewedSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="Mark announcement as viewed",
        operation_description="Mark a specific announcement as viewed by the current user.",
        request_body=MarkAnnouncementViewedSerializer,
        responses={
            200: "Announcement marked as viewed",
            404: "Announcement not found",
            401: "Unauthorized"
        }
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        announcement_id = serializer.validated_data['announcement_id']
        
        try:
            announcement = Announcement.objects.get(id=announcement_id)
            
            # Create or get the view record
            view_record, created = AnnouncementView.objects.get_or_create(
                announcement=announcement,
                user=request.user
            )
            
            # Increment view count if newly created
            if created:
                announcement.increment_view_count()
            
            return success_response(
                message="Announcement marked as viewed",
                data={
                    'announcement_id': str(announcement_id),
                    'viewed_at': view_record.viewed_at.isoformat()
                }
            )
            
        except Announcement.DoesNotExist:
            return bad_request_response(
                message="Announcement not found",
                status_code=404
            )


# Admin endpoints for managing announcements

class AdminAnnouncementListCreateView(generics.ListCreateAPIView):
    """
    Admin endpoint to list all announcements and create new ones.
    """
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAdminUser]
    queryset = Announcement.objects.all().order_by('-created_at')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AnnouncementCreateSerializer
        return AnnouncementSerializer
    
    @swagger_auto_schema(
        operation_summary="[Admin] List all announcements",
        operation_description="Admin endpoint to retrieve all announcements regardless of status.",
        responses={
            200: AnnouncementSerializer(many=True),
            401: "Unauthorized",
            403: "Forbidden - Admin access required"
        }
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filter by target audience if specified
        target_audience = request.query_params.get('target_audience')
        if target_audience:
            queryset = queryset.filter(target_audience=target_audience)
        
        # Filter by status
        is_published = request.query_params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')
        
        return paginate_success_response_with_serializer(
            request,
            AnnouncementSerializer,
            queryset,
            page_size=int(request.GET.get('page_size', 20))
        )
    
    @swagger_auto_schema(
        operation_summary="[Admin] Create new announcement",
        operation_description="Admin endpoint to create a new announcement. Optionally sends push notifications to target audience.",
        request_body=AnnouncementCreateSerializer,
        responses={
            201: AnnouncementSerializer(),
            400: "Bad request - validation error",
            401: "Unauthorized",
            403: "Forbidden - Admin access required"
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = AnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create announcement
        announcement = serializer.save(created_by=request.user)
        
        # Send push notifications if requested
        if announcement.send_push_notification and announcement.is_published:
            self._send_push_notifications(announcement)
        
        return success_response(
            message="Announcement created successfully",
            data=AnnouncementSerializer(announcement, context={'request': request}).data,
            status_code=201
        )
    
    def _send_push_notifications(self, announcement):
        """Send push notifications to target audience"""
        from account.models import User
        
        try:
            # Determine target users
            if announcement.target_audience == 'all':
                users = User.objects.filter(is_active=True)
            else:
                users = User.objects.filter(
                    role=announcement.target_audience,
                    is_active=True
                )
            
            # Send notifications asynchronously
            for user in users:
                try:
                    notification_helper.send_to_user_async(
                        user=user,
                        title=announcement.title,
                        body=announcement.message,
                        data={
                            "type": "announcement",
                            "announcement_id": str(announcement.id),
                            "priority": announcement.priority,
                            "action_url": announcement.action_url or "",
                            "screen": "announcements"
                        }
                    )
                except Exception as e:
                    print(f"Failed to send notification to user {user.id}: {e}")
                    
        except Exception as e:
            print(f"Error sending push notifications: {e}")


class AdminAnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin endpoint to retrieve, update, or delete a specific announcement.
    """
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAdminUser]
    queryset = Announcement.objects.all()
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AnnouncementCreateSerializer
        return AnnouncementSerializer
    
    @swagger_auto_schema(
        operation_summary="[Admin] Get announcement details",
        responses={
            200: AnnouncementSerializer(),
            404: "Announcement not found",
            401: "Unauthorized",
            403: "Forbidden - Admin access required"
        }
    )
    def get(self, request, *args, **kwargs):
        announcement = self.get_object()
        serializer = self.get_serializer(announcement)
        return success_response(data=serializer.data)
    
    @swagger_auto_schema(
        operation_summary="[Admin] Update announcement",
        request_body=AnnouncementCreateSerializer,
        responses={
            200: AnnouncementSerializer(),
            400: "Bad request - validation error",
            404: "Announcement not found",
            401: "Unauthorized",
            403: "Forbidden - Admin access required"
        }
    )
    def put(self, request, *args, **kwargs):
        announcement = self.get_object()
        serializer = AnnouncementCreateSerializer(
            announcement,
            data=request.data,
            partial=False
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return success_response(
            message="Announcement updated successfully",
            data=AnnouncementSerializer(announcement, context={'request': request}).data
        )
    
    @swagger_auto_schema(
        operation_summary="[Admin] Partially update announcement",
        request_body=AnnouncementCreateSerializer,
        responses={
            200: AnnouncementSerializer(),
            400: "Bad request - validation error",
            404: "Announcement not found",
            401: "Unauthorized",
            403: "Forbidden - Admin access required"
        }
    )
    def patch(self, request, *args, **kwargs):
        announcement = self.get_object()
        serializer = AnnouncementCreateSerializer(
            announcement,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return success_response(
            message="Announcement updated successfully",
            data=AnnouncementSerializer(announcement, context={'request': request}).data
        )
    
    @swagger_auto_schema(
        operation_summary="[Admin] Delete announcement",
        responses={
            200: "Announcement deleted successfully",
            404: "Announcement not found",
            401: "Unauthorized",
            403: "Forbidden - Admin access required"
        }
    )
    def delete(self, request, *args, **kwargs):
        announcement = self.get_object()
        announcement.delete()
        
        return success_response(
            message="Announcement deleted successfully"
        )


@swagger_auto_schema(
    method='post',
    operation_summary="[Admin] Publish announcement",
    operation_description="Admin endpoint to publish an announcement and optionally send push notifications.",
    responses={
        200: "Announcement published successfully",
        404: "Announcement not found",
        401: "Unauthorized",
        403: "Forbidden - Admin access required"
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_publish_announcement(request, announcement_id):
    """
    Admin endpoint to publish an announcement.
    """
    try:
        announcement = Announcement.objects.get(id=announcement_id)
        announcement.is_published = True
        announcement.save()
        
        # Send push notifications if enabled
        if announcement.send_push_notification:
            AdminAnnouncementListCreateView()._send_push_notifications(announcement)
        
        return success_response(
            message="Announcement published successfully",
            data=AnnouncementSerializer(announcement, context={'request': request}).data
        )
        
    except Announcement.DoesNotExist:
        return bad_request_response(
            message="Announcement not found",
            status_code=404
        )
