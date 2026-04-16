from django.urls import path
from admin_manager.views.announcements import (
    AnnouncementListView,
    AnnouncementDetailView,
    MarkAnnouncementAsViewedView,
    AdminAnnouncementListCreateView,
    AdminAnnouncementDetailView,
    admin_publish_announcement
)
from admin_manager.views.popup_announcements import (
    ActivePopupAnnouncementView,
    PopupAnnouncementDetailView,
    MarkPopupClickedView,
    AdminPopupAnnouncementListCreateView,
    AdminPopupAnnouncementDetailView
)

urlpatterns = [
    # User endpoints
    path('announcements/', AnnouncementListView.as_view(), name='announcement-list'),
    path('announcements/<uuid:id>/', AnnouncementDetailView.as_view(), name='announcement-detail'),
    path('announcements/mark-viewed/', MarkAnnouncementAsViewedView.as_view(), name='announcement-mark-viewed'),
    
    # Admin endpoints
    path('admin/announcements/', AdminAnnouncementListCreateView.as_view(), name='admin-announcement-list-create'),
    path('admin/announcements/<uuid:id>/', AdminAnnouncementDetailView.as_view(), name='admin-announcement-detail'),
    path('admin/announcements/<uuid:announcement_id>/publish/', admin_publish_announcement, name='admin-announcement-publish'),

    # Popup Announcements
    path('popups/active/', ActivePopupAnnouncementView.as_view(), name='active-popup-list'),
    path('popups/<uuid:id>/', PopupAnnouncementDetailView.as_view(), name='popup-detail'),
    path('popups/<uuid:id>/click/', MarkPopupClickedView.as_view(), name='popup-click-record'),

    # Admin Popup Announcements
    path('admin/popups/', AdminPopupAnnouncementListCreateView.as_view(), name='admin-popup-list-create'),
    path('admin/popups/<uuid:id>/', AdminPopupAnnouncementDetailView.as_view(), name='admin-popup-detail'),
]
