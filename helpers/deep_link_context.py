"""
Deep Link Template Context Processors

Provides deep linking context data to Django templates.
"""

from django.conf import settings
from .deep_link_utils import MobileDetection


def deep_link_context(request):
    """
    Add deep linking context to templates.
    """
    try:
        # Get device information
        device_info = MobileDetection.get_device_info(request)
        
        # Get deep linking configuration
        deep_link_config = getattr(settings, 'DEEP_LINK_CONFIG', {})
        
        # Check if deep linking is enabled
        deep_linking_enabled = getattr(settings, 'ENABLE_DEEP_LINKING', True)
        smart_banners_enabled = getattr(settings, 'ENABLE_SMART_BANNERS', True)
        
        # Get app store URLs
        ios_app_store_url = getattr(settings, 'IOS_APP_STORE_URL', '')
        android_play_store_url = getattr(settings, 'ANDROID_PLAY_STORE_URL', '')
        
        # Get app information
        app_name = getattr(settings, 'APP_NAME', 'FindMyTaste')
        app_description = getattr(settings, 'APP_DESCRIPTION', 'Discover amazing food and restaurants')
        
        # Determine appropriate app store URL based on platform
        app_store_url = ''
        if device_info['platform'] == 'ios':
            app_store_url = ios_app_store_url
        elif device_info['platform'] == 'android':
            app_store_url = android_play_store_url
        
        # Check if user has dismissed smart banner
        banner_dismissed = request.COOKIES.get('banner_dismissed') == 'true'
        
        # Check user preference for app redirects
        prefer_app = request.COOKIES.get('prefer_app', 'true') == 'true'
        
        context = {
            'deep_linking': {
                'enabled': deep_linking_enabled,
                'smart_banners_enabled': smart_banners_enabled,
                'device_info': device_info,
                'app_name': app_name,
                'app_description': app_description,
                'app_store_url': app_store_url,
                'ios_app_store_url': ios_app_store_url,
                'android_play_store_url': android_play_store_url,
                'banner_dismissed': banner_dismissed,
                'prefer_app': prefer_app,
                'config': deep_link_config,
            }
        }
        
        return context
        
    except Exception as e:
        # Return empty context if there's an error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in deep_link_context: {e}")
        
        return {
            'deep_linking': {
                'enabled': False,
                'error': str(e)
            }
        }