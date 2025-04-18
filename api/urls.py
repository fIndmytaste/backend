from django.urls import path, include


urlpatterns = [ 
    path('account/',include("account.urls.account")),
    path('admin-manager/',include("admin_manager.urls")),
    path('auth/',include("account.urls.auth")),
    path('products/',include("product.urls")),
    path('vendor/',include("vendor.urls")),
    path('wallet/',include("wallet.urls")),
]
