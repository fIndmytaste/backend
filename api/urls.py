from django.urls import re_path
from admin_manager.views.announcements import (
    AnnouncementListView,
    AnnouncementDetailView,
    MarkAnnouncementAsViewedView
)
from admin_manager.views.popup_announcements import (
    ActivePopupAnnouncementView,
    PopupAnnouncementDetailView,
    MarkPopupClickedView,
)

from django.urls import path, include
from account.views.account import send_notification
from rest_framework.routers import DefaultRouter
from api.views import (
    CustomerInProgressOrdersListView, 
    CustomerOrdersListView, 
    GetAllBanksView, 
    TestPushNotificationView, 
    TestingWebsocketView, 
    ValidateBankAccountNumber,
    RedisHealthCheckView
)
from rider.views import ConfirmOrderPaymentAPIView, EnhancedRiderViewSet, MakeOrderPayment, NearbyRidersView, OrderPaymentWebhookView, OrderTrackingDetailView, OrderViewSet, RiderGuarantorUpdateView, RiderOrderDetailView, RiderViewSet, UploadRiderDocumentView, WebSocketSimulationView
from vendor.views import AllMarketPlaceCategoriesView,SingleMarketPlaceCategoryVendorsView, SingleMarketPlaceCategoryView



router = DefaultRouter()
router.register(r'orders', OrderViewSet)
router.register(r'riders', RiderViewSet)
router.register(r'riders-v1', EnhancedRiderViewSet,basename='enhanced-rider')



urlpatterns = [ 
    path('account/',include("account.urls.account")),
    path('admin-manager/',include("admin_manager.urls")),
    # User-friendly announcement endpoints
    path('announcements/', AnnouncementListView.as_view(), name='announcement-list'),
    path('announcements/<uuid:id>/', AnnouncementDetailView.as_view(), name='announcement-detail'),
    path('announcements/mark-viewed/', MarkAnnouncementAsViewedView.as_view(), name='announcement-mark-viewed'),
    # Popup Announcements (user-facing)
    path('popups/active/', ActivePopupAnnouncementView.as_view(), name='active-popup-list'),
    path('popups/<uuid:id>/', PopupAnnouncementDetailView.as_view(), name='popup-detail'),
    path('popups/<uuid:id>/click/', MarkPopupClickedView.as_view(), name='popup-click-record'),
    path('auth/',include("account.urls.auth")),
    path('products/',include("product.urls")),
    path('vendor/',include("vendor.urls")),
    path('vendors/',include("vendor.urls")),
    path('wallet/',include("wallet.urls")),
    # path('marketplace/vendors', AllMarketPlaceVendorsView.as_view(), name='AllMarketPlaceVendorsView'),
    path('marketplace/categories', AllMarketPlaceCategoriesView.as_view(), name='AllMarketPlaceCategoriesView'),
    path('marketplace/categories/<category_id>', SingleMarketPlaceCategoryView.as_view(), name='SingleMarketPlaceCategoryDetailsView'),
    path('marketplace/categories/<category_id>/vendors', SingleMarketPlaceCategoryVendorsView.as_view(), name='SingleMarketPlaceCategoryDetailsView'),
    path('riders/<id>/upload_documents/',UploadRiderDocumentView.as_view()),
    path('riders/<id>/guarantors/',RiderGuarantorUpdateView.as_view()),
    path('riders/orders/<order_id>/', RiderOrderDetailView.as_view()),
    path('api/orders/<uuid:order_id>/tracking/', OrderTrackingDetailView.as_view(), name='order-tracking'),
    path('api/nearby-riders/', NearbyRidersView.as_view(), name='nearby-riders'),
    path('order/<id>/make-payment',MakeOrderPayment.as_view()),
    path('order/confirm-payment',ConfirmOrderPaymentAPIView.as_view()),
    path('order/make-payment-webhook',OrderPaymentWebhookView.as_view()),
    path('orders',CustomerOrdersListView.as_view()),
    path('orders/in-progress', CustomerInProgressOrdersListView.as_view(), name='customer-orders-in-progress-list'),
    path('main/get-all-banks',GetAllBanksView.as_view()),
    path('main/resolve-account-number',ValidateBankAccountNumber.as_view()),
    path('', include(router.urls)),
    path('', include(('helpers.deep_link_urls', 'deep_link'), namespace='deep_link')),
    path('notifications/send/', send_notification, name='send_notification'),
    path('websocket/test', TestingWebsocketView.as_view(), name='TestingWebsocketView'),
    path('websocket/simulate', WebSocketSimulationView.as_view(), name='websocket_simulation'),
    path('push-notification/test', TestPushNotificationView.as_view(), name='test_push_notification'),
    path('redis/test', RedisHealthCheckView.as_view(), name='redis_health_check'),
    
    # Backblaze test endpoints
    path('test/backblaze/', include('helpers.test_urls')),
]
