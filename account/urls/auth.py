from django.urls import path
from account.views.auth import LoginAPIView, PasswordResetConfirmView, PasswordResetRequestView


urlpatterns = [ 
    path('login', LoginAPIView.as_view(), name='login'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
