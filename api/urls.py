from django.urls import path, include
from account.views.account import send_notification
from rest_framework.routers import DefaultRouter
from api.views import GetAllBanksView, ValidateBankAccountNumber
from rider.views import EnhancedRiderViewSet, MakeOrderPayment, NearbyRidersView, OrderPaymentWebhookView, OrderTrackingDetailView, OrderViewSet, RiderOrderDetailView, RiderViewSet, UploadRiderDocumentView



router = DefaultRouter()
router.register(r'orders', OrderViewSet)
router.register(r'riders', RiderViewSet)
router.register(r'riders-v1', EnhancedRiderViewSet,basename='enhanced-rider')



urlpatterns = [ 
    path('account/',include("account.urls.account")),
    path('admin-manager/',include("admin_manager.urls")),
    path('auth/',include("account.urls.auth")),
    path('products/',include("product.urls")),
    path('vendor/',include("vendor.urls")),
    path('vendors/',include("vendor.urls")),
    path('wallet/',include("wallet.urls")),
    path('riders/<id>/upload_documents/',UploadRiderDocumentView.as_view()),
    path('riders/orders/<order_id>',RiderOrderDetailView.as_view()),
    path('api/orders/<uuid:order_id>/tracking/', OrderTrackingDetailView.as_view(), name='order-tracking'),
    path('api/nearby-riders/', NearbyRidersView.as_view(), name='nearby-riders'),
    path('order/<id>/make-payment',MakeOrderPayment.as_view()),
    path('order/make-payment-webhook',OrderPaymentWebhookView.as_view()),
    path('main/get-all-banks',GetAllBanksView.as_view()),
    path('main/resolve-account-number',ValidateBankAccountNumber.as_view()),
    path('', include(router.urls)),
    path('notifications/send/', send_notification, name='send_notification'),
]
