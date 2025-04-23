from django.urls import path
from account.views import auth as auth_view
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

urlpatterns = [ 
    path('login', auth_view.LoginAPIView.as_view(), name='login'),
    path('refresh-token', TokenRefreshView.as_view(), name='token_refresh'),
    path('buyer-register', auth_view.RegisterAPIView.as_view(), name='buyer-register'),
    path('vendor-register', auth_view.RegisterVendorAPIView.as_view(), name='vendor-register'),
    path('rider-register', auth_view.RegisterRiderAPIView.as_view(), name='rider-register'),
    path('resend-otp', auth_view.ResendOTPAPIView.as_view(), name='resend-otp'),
    path('resend-otp-login', auth_view.ResendOTPLoginAPIView.as_view(), name='resend-ot-login'),
    path('verify', auth_view.RegisterAccountVerifyAPIView.as_view(), name='vendor-register'),
    path('verify-login', auth_view.VerifyOTPAPIView.as_view(), name='verify-otp'),
    path('password/reset/', auth_view.PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/<uidb64>/<token>/', auth_view.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
