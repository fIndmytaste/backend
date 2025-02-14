from django.urls import path, include


urlpatterns = [ 
    path('account/',include("account.urls.account")),
    path('auth/',include("account.urls.account")),
]
