from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import GetAllBanksView, ValidateBankAccountNumber
from rider.views import MakeOrderPayment, OrderViewSet, RiderOrderDetailView, RiderViewSet, UploadRiderDocumentView



router = DefaultRouter()
router.register(r'orders', OrderViewSet)
router.register(r'riders', RiderViewSet)



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
    path('order/<id>/make-payment',MakeOrderPayment.as_view()),
    path('main/get-all-banks',GetAllBanksView.as_view()),
    path('main/resolve-account-number',ValidateBankAccountNumber.as_view()),
    path('', include(router.urls)),
]
