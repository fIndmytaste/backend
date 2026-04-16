"""
Deep Link Settings Configuration for FindMyTaste App

This file contains all the configuration settings for deep linking functionality.
Import these settings in your Django settings.py file.
"""

# Deep Link Configuration
DEEP_LINK_CONFIG = {
    # App Information
    'APP_NAME': 'FindMyTaste',
    'APP_DESCRIPTION': 'Discover amazing food and restaurants near you',
    
    # URL Schemes
    'IOS_URL_SCHEME': 'findmytaste',
    'ANDROID_URL_SCHEME': 'findmytaste',
    'UNIVERSAL_URL_SCHEME': 'https://findmytaste.app',
    
    # App Store URLs
    'IOS_APP_STORE_URL': 'https://apps.apple.com/app/findmytaste/id123456789',
    'ANDROID_PLAY_STORE_URL': 'https://play.google.com/store/apps/details?id=com.findmytaste.app',
    
    # App Package Information
    'IOS_APP_ID': 'TEAMID.com.findmytaste.app',
    'ANDROID_PACKAGE_NAME': 'com.findmytaste.app',
    'ANDROID_CERT_FINGERPRINT': 'AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99',
    
    # Feature Toggles
    'ENABLE_DEEP_LINKING': True,
    'ENABLE_SMART_BANNERS': True,
    'ENABLE_AUTO_REDIRECTS': True,
    'ENABLE_QR_CODES': True,
    'ENABLE_ANALYTICS': True,
    'ENABLE_SHARE_LINKS': True,
    
    # Redirect Behavior
    'DEFAULT_FALLBACK_DELAY': 3000,  # milliseconds
    'APP_OPEN_TIMEOUT': 2000,  # milliseconds
    'BANNER_DISMISS_DURATION': 86400,  # seconds (24 hours)
    
    # Analytics
    'ANALYTICS_RETENTION_DAYS': 30,
    'ENABLE_REAL_TIME_ANALYTICS': True,
    
    # QR Code Settings
    'QR_CODE_DEFAULT_SIZE': 'medium',
    'QR_CODE_BRAND_COLOR': '#667eea',
    'QR_CODE_ERROR_CORRECTION': 'L',
    
    # Universal Links
    'UNIVERSAL_LINK_PATHS': [
        '/dl/*',
        '/app/*',
        '/share/*',
        '/product/*',
        '/vendor/*',
        '/order/*'
    ],
    
    # Supported Routes
    'SUPPORTED_ROUTES': {
        'marketplace': {
            'title': 'Marketplace',
            'description': 'Browse restaurants and food options',
            'icon': '🏪',
            'requires_auth': False
        },
        'product_detail': {
            'title': 'Product Details',
            'description': 'View product information',
            'icon': '🍽️',
            'requires_auth': False,
            'params': ['product_id']
        },
        'vendor_profile': {
            'title': 'Restaurant Profile',
            'description': 'View restaurant details and menu',
            'icon': '🏪',
            'requires_auth': False,
            'params': ['vendor_id']
        },
        'category_products': {
            'title': 'Category',
            'description': 'Browse products by category',
            'icon': '📂',
            'requires_auth': False,
            'params': ['category_id']
        },
        'login': {
            'title': 'Login',
            'description': 'Sign in to your account',
            'icon': '🔐',
            'requires_auth': False
        },
        'register': {
            'title': 'Sign Up',
            'description': 'Create a new account',
            'icon': '📝',
            'requires_auth': False
        },
        'verify_otp': {
            'title': 'Verify Account',
            'description': 'Verify your phone number',
            'icon': '✅',
            'requires_auth': False,
            'params': ['phone', 'otp']
        },
        'reset_password': {
            'title': 'Reset Password',
            'description': 'Reset your account password',
            'icon': '🔑',
            'requires_auth': False,
            'params': ['token']
        },
        'order_detail': {
            'title': 'Order Details',
            'description': 'View your order information',
            'icon': '📦',
            'requires_auth': True,
            'params': ['order_id']
        },
        'order_history': {
            'title': 'Order History',
            'description': 'View your past orders',
            'icon': '📋',
            'requires_auth': True
        },
        'order_tracking': {
            'title': 'Track Order',
            'description': 'Track your current order',
            'icon': '🚚',
            'requires_auth': True,
            'params': ['order_id']
        },
        'profile': {
            'title': 'Profile',
            'description': 'Manage your account',
            'icon': '👤',
            'requires_auth': True
        },
        'wallet': {
            'title': 'Wallet',
            'description': 'Manage your wallet and payments',
            'icon': '💳',
            'requires_auth': True
        },
        'notifications': {
            'title': 'Notifications',
            'description': 'View your notifications',
            'icon': '🔔',
            'requires_auth': True
        },
        'vendor_dashboard': {
            'title': 'Vendor Dashboard',
            'description': 'Manage your restaurant',
            'icon': '📊',
            'requires_auth': True,
            'user_type': 'vendor'
        },
        'rider_dashboard': {
            'title': 'Rider Dashboard',
            'description': 'Manage your deliveries',
            'icon': '🏍️',
            'requires_auth': True,
            'user_type': 'rider'
        },
        'cart': {
            'title': 'Shopping Cart',
            'description': 'Review your cart',
            'icon': '🛒',
            'requires_auth': False
        },
        'checkout': {
            'title': 'Checkout',
            'description': 'Complete your order',
            'icon': '💳',
            'requires_auth': True
        },
        'search': {
            'title': 'Search',
            'description': 'Search for food and restaurants',
            'icon': '🔍',
            'requires_auth': False,
            'params': ['query', 'category', 'location']
        }
    },
    
    # Mobile App Detection
    'MOBILE_USER_AGENTS': [
        r'Mobile', r'Android', r'iPhone', r'iPad', r'iPod',
        r'BlackBerry', r'Windows Phone', r'Opera Mini',
        r'IEMobile', r'Mobile Safari', r'webOS', r'Kindle'
    ],
    
    # App User Agent Patterns
    'APP_USER_AGENTS': [
        r'FindMyTaste', r'findmytaste'
    ],
    
    # Routes that should trigger app redirects
    'AUTO_REDIRECT_ROUTES': [
        r'^/api/v1/products/\d+/$',
        r'^/api/v1/vendor/\d+/$',
        r'^/api/v1/orders/\d+/$',
        r'^/api/v1/auth/login/$',
        r'^/api/v1/auth/register/$',
        r'^/api/v1/marketplace/$',
        r'^/api/v1/wallet/$',
    ],
    
    # Routes to exclude from app redirects
    'EXCLUDE_REDIRECT_ROUTES': [
        r'^/admin/',
        r'^/swagger/',
        r'^/redoc/',
        r'^/dl/',
        r'^/app/',
        r'^/download/',
        r'^/api/v1/.*\.(json|xml)$',
        r'^/static/',
        r'^/media/',
    ],
    
    # Smart Banner Configuration
    'SMART_BANNER_CONFIG': {
        'show_on_mobile': True,
        'show_on_tablet': False,
        'auto_hide_delay': None,  # Set to number of seconds to auto-hide
        'dismiss_duration': 86400,  # 24 hours
        'custom_css': {
            'background_color': '#f8f9fa',
            'text_color': '#333',
            'button_color': '#667eea',
            'button_text_color': '#fff',
            'border_color': '#dee2e6'
        }
    },
    
    # Social Sharing
    'SOCIAL_SHARING': {
        'default_image': '/static/images/app-icon.png',
        'twitter_handle': '@findmytaste',
        'facebook_app_id': '123456789',
        'enable_og_tags': True,
        'enable_twitter_cards': True
    },
    
    # Security
    'SECURITY': {
        'validate_referrer': True,
        'allowed_referrers': [
            'findmytaste.com',
            'www.findmytaste.com',
            'app.findmytaste.com'
        ],
        'rate_limit_per_ip': 100,  # requests per hour
        'enable_csrf_protection': True
    }
}

# Django Settings Integration
def configure_deep_linking_settings(settings_dict):
    """
    Configure Django settings for deep linking.
    Call this function in your settings.py file.
    """
    
    # Add deep linking configuration
    for key, value in DEEP_LINK_CONFIG.items():
        settings_dict[key] = value
    
    # Add middleware
    middleware = settings_dict.get('MIDDLEWARE', [])
    
    # Add deep link middleware (should be early in the list)
    deep_link_middlewares = [
        'helpers.deep_link_middleware.DeepLinkMiddleware',
        'helpers.deep_link_middleware.SmartBannerMiddleware',
    ]
    
    for middleware_class in reversed(deep_link_middlewares):
        if middleware_class not in middleware:
            # Insert after SecurityMiddleware if it exists
            try:
                security_index = middleware.index('django.middleware.security.SecurityMiddleware')
                middleware.insert(security_index + 1, middleware_class)
            except ValueError:
                # Insert at the beginning if SecurityMiddleware not found
                middleware.insert(0, middleware_class)
    
    settings_dict['MIDDLEWARE'] = middleware
    
    # Add template context processors
    templates = settings_dict.get('TEMPLATES', [])
    for template_config in templates:
        if template_config.get('BACKEND') == 'django.template.backends.django.DjangoTemplates':
            context_processors = template_config.setdefault('OPTIONS', {}).setdefault('context_processors', [])
            
            deep_link_processors = [
                'helpers.deep_link_context.deep_link_context',
            ]
            
            for processor in deep_link_processors:
                if processor not in context_processors:
                    context_processors.append(processor)
    
    # Add static files configuration
    staticfiles_dirs = settings_dict.get('STATICFILES_DIRS', [])
    deep_link_static_dir = 'helpers/static'
    if deep_link_static_dir not in staticfiles_dirs:
        staticfiles_dirs.append(deep_link_static_dir)
    settings_dict['STATICFILES_DIRS'] = staticfiles_dirs
    
    return settings_dict


# Example usage in settings.py:
"""
# At the bottom of your settings.py file:
from helpers.deep_link_settings import configure_deep_linking_settings
globals().update(configure_deep_linking_settings(globals()))
"""