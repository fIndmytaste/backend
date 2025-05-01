from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rider.views import OrderViewSet, RiderViewSet



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
    path('', include(router.urls)),
]
