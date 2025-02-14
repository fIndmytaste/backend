from django.urls import path, include


urlpatterns = [ 
    path('account/',include("account.urls.account")),
    path('auth/',include("account.urls.account")),
    path('products/',include("product.urls")),
    path('vendor/',include("vendor.urls")),
]
