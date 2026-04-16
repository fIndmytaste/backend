"""
Deep Link URL Patterns for FindMyTaste App

This module defines URL patterns for handling deep link redirects
and mobile app integration.
"""

from django.urls import path, re_path
from . import deep_link_views

app_name = 'deep_links'

urlpatterns = [
    # General deep link handler
    path('dl/<str:route>/', deep_link_views.DeepLinkRedirectView.as_view(), name='deep_link_redirect'),
    
    # Authentication deep links
    path('dl/auth/login/', deep_link_views.AuthDeepLinkView.as_view(), {'auth_type': 'login'}, name='auth_login'),
    path('dl/auth/register/', deep_link_views.AuthDeepLinkView.as_view(), {'auth_type': 'register'}, name='auth_register'),
    path('dl/auth/verify/', deep_link_views.AuthDeepLinkView.as_view(), {'auth_type': 'verify_account'}, name='auth_verify'),
    path('dl/auth/reset-password/', deep_link_views.AuthDeepLinkView.as_view(), {'auth_type': 'reset_password'}, name='auth_reset_password'),
    
    # Product deep links
    path('dl/product/<str:product_id>/', deep_link_views.ProductDeepLinkView.as_view(), name='product_detail'),
    path('dl/category/<str:category_id>/', deep_link_views.CategoryDeepLinkView.as_view(), name='category_detail'),
    path('dl/vendor/<str:vendor_id>/', deep_link_views.VendorDeepLinkView.as_view(), name='vendor_profile'),
    
    # Order deep links
    path('dl/order/<str:order_id>/', deep_link_views.OrderDeepLinkView.as_view(), name='order_detail'),
    path('dl/order/<str:order_id>/tracking/', deep_link_views.OrderTrackingDeepLinkView.as_view(), name='order_tracking'),
    
    # User profile deep links
    path('dl/profile/', deep_link_views.ProfileDeepLinkView.as_view(), name='profile'),
    path('dl/wallet/', deep_link_views.WalletDeepLinkView.as_view(), name='wallet'),
    
    # Rider deep links
    path('dl/rider/dashboard/', deep_link_views.RiderDashboardDeepLinkView.as_view(), name='rider_dashboard'),
    path('dl/rider/order/<str:order_id>/', deep_link_views.RiderOrderDeepLinkView.as_view(), name='rider_order_detail'),
    
    # Vendor deep links
    path('dl/vendor/dashboard/', deep_link_views.VendorDashboardDeepLinkView.as_view(), name='vendor_dashboard'),
    
    # Marketplace deep links
    path('dl/marketplace/', deep_link_views.MarketplaceDeepLinkView.as_view(), name='marketplace'),
    
    # Notification deep links
    path('dl/notifications/', deep_link_views.NotificationDeepLinkView.as_view(), name='notifications'),
    
    # Universal link handlers (for iOS universal links)
    path('app/<str:route>/', deep_link_views.UniversalLinkView.as_view(), name='universal_link'),
    
    # App store redirects
    path('download/', deep_link_views.AppDownloadView.as_view(), name='app_download'),
    path('download/ios/', deep_link_views.AppDownloadView.as_view(), {'platform': 'ios'}, name='ios_download'),
    path('download/android/', deep_link_views.AppDownloadView.as_view(), {'platform': 'android'}, name='android_download'),
    
    # QR code generation for deep links
    path('qr/<str:route>/', deep_link_views.QRCodeView.as_view(), name='qr_code'),
    
    # Share link generator
    path('share/<str:route>/', deep_link_views.ShareLinkView.as_view(), name='share_link'),
    
    # Mobile app bridge for testing
    path('mobile-app-bridge/', deep_link_views.MobileAppBridgeView.as_view(), name='mobile_app_bridge'),
]