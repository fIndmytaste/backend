from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from admin_manager.models import PopupAnnouncement, PopupAnnouncementView
from admin_manager.serializers.popup_announcements import (
    PopupAnnouncementSerializer,
    PopupAnnouncementCreateSerializer
)
from helpers.response.response_format import (
    success_response,
    bad_request_response,
    paginate_success_response_with_serializer
)


class ActivePopupAnnouncementView(generics.ListAPIView):
    """
    Get active popup announcements for the current user.
    Usually only one should be displayed at a time.
    """
    serializer_class = PopupAnnouncementSerializer
    permission_classes = []

    def get_queryset(self):
        user = self.request.user
        user_role = self.request.GET.get('role', 'customer')
        now = timezone.now()

        # Build query for active popups
        queryset = PopupAnnouncement.objects.filter(
            is_active=True,
            is_published=True,
            # start_date__lte=now
        )
        
        # .filter(
        #     Q(end_date__isnull=True) | Q(end_date__gte=now)
        # ).filter(
        #     Q(target_audience='all') | Q(target_audience=user_role)
        # )

        return queryset.order_by('-created_at')

    @swagger_auto_schema(
        operation_summary="Get active popups",
        operation_description="Retrieve active popup announcements for the current user/role.",
        responses={200: PopupAnnouncementSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filter out popups already viewed if show_once_per_user is True
        if request.user.is_authenticated:
            viewed_popup_ids = PopupAnnouncementView.objects.filter(
                user=request.user
            ).values_list('popup_id', flat=True)
            
            # This is a bit tricky with querysets, let's filter in Python or use exclude
            # Actually, we can use exclude
            queryset = queryset.exclude(
                id__in=viewed_popup_ids,
                show_once_per_user=True
            )

        serializer = self.serializer_class(queryset, many=True, context={'request': request})
        return success_response(data=serializer.data)


class PopupAnnouncementDetailView(generics.RetrieveAPIView):
    """
    Get details of a popup and increment view count.
    """
    serializer_class = PopupAnnouncementSerializer
    permission_classes = []
    lookup_field = 'id'
    queryset = PopupAnnouncement.objects.all()

    def get(self, request, *args, **kwargs):
        try:
            popup = self.get_object()
            popup.increment_view_count()

            if request.user.is_authenticated:
                PopupAnnouncementView.objects.get_or_create(
                    popup=popup,
                    user=request.user
                )

            serializer = self.get_serializer(popup)
            return success_response(data=serializer.data)
        except PopupAnnouncement.DoesNotExist:
            return bad_request_response(message="Popup not found", status_code=404)


class MarkPopupClickedView(generics.GenericAPIView):
    """
    Increment click count for a popup.
    """
    permission_classes = []

    def post(self, request, id):
        try:
            popup = PopupAnnouncement.objects.get(id=id)
            popup.increment_click_count()
            return success_response(message="Click recorded")
        except PopupAnnouncement.DoesNotExist:
            return bad_request_response(message="Popup not found", status_code=404)


# Admin Views
class AdminPopupAnnouncementListCreateView(generics.ListCreateAPIView):
    serializer_class = PopupAnnouncementSerializer
    permission_classes = [IsAdminUser]
    queryset = PopupAnnouncement.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PopupAnnouncementCreateSerializer
        return PopupAnnouncementSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        popup = serializer.save(created_by=request.user)
        return success_response(
            message="Popup created successfully",
            data=PopupAnnouncementSerializer(popup, context={'request': request}).data,
            status_code=201
        )


class AdminPopupAnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PopupAnnouncementSerializer
    permission_classes = [IsAdminUser]
    queryset = PopupAnnouncement.objects.all()
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PopupAnnouncementCreateSerializer
        return PopupAnnouncementSerializer
