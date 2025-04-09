from django.urls import path
from account.views.auth import LoginAPIView, PasswordResetConfirmView, PasswordResetRequestView, RegisterAPIView, RegisterAccountVerifyAPIView, RegisterVendorAPIView, ResendOTPAPIView, VerifyOTPAPIView


urlpatterns = [ 
    path('login', LoginAPIView.as_view(), name='login'),
    path('buyer-register', RegisterAPIView.as_view(), name='buyer-register'),
    path('vendor-register', RegisterVendorAPIView.as_view(), name='vendor-register'),
    path('rider-register', RegisterVendorAPIView.as_view(), name='vendor-register'),
    path('resend-otp', ResendOTPAPIView.as_view(), name='resend-otp'),
    path('verify', RegisterAccountVerifyAPIView.as_view(), name='vendor-register'),
    path('verify-login', VerifyOTPAPIView.as_view(), name='verify-otp'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
