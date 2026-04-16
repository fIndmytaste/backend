"""
Deep Linking Helper Module for FindMyTaste App

This module provides utilities for generating and handling deep links
that can redirect users from web URLs to mobile app screens.
"""

import urllib.parse
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class DeepLinkManager:
    """
    Manages deep link generation and handling for the FindMyTaste app.
    """
    
    # App URL schemes for different platforms
    APP_SCHEMES = {
        'ios': 'findmytaste://',
        'android': 'findmytaste://',
        'universal': 'https://findmytaste.app/'  # Universal links fallback
    }
    
    # Deep link route mappings
    DEEP_LINK_ROUTES = {
        # Authentication routes
        'login': 'auth/login',
        'register': 'auth/register',
        'verify_account': 'auth/verify',
        'reset_password': 'auth/reset-password',
        
        # User profile routes
        'profile': 'profile',
        'edit_profile': 'profile/edit',
        
        # Product and marketplace routes
        'product_detail': 'product/{product_id}',
        'category': 'category/{category_id}',
        'vendor_profile': 'vendor/{vendor_id}',
        'marketplace': 'marketplace',
        
        # Order routes
        'order_detail': 'order/{order_id}',
        'order_tracking': 'order/{order_id}/tracking',
        'order_history': 'orders',
        
        # Rider routes
        'rider_dashboard': 'rider/dashboard',
        'rider_orders': 'rider/orders',
        'rider_order_detail': 'rider/order/{order_id}',
        
        # Vendor routes
        'vendor_dashboard': 'vendor/dashboard',
        'vendor_products': 'vendor/products',
        'vendor_orders': 'vendor/orders',
        
        # Wallet routes
        'wallet': 'wallet',
        'wallet_transactions': 'wallet/transactions',
        
        # Notifications
        'notifications': 'notifications',
    }
    
    @classmethod
    def generate_deep_link(cls, route: str, platform: str = 'universal', **params) -> str:
        """
        Generate a deep link URL for the specified route and platform.
        
        Args:
            route: The route key from DEEP_LINK_ROUTES
            platform: Target platform ('ios', 'android', 'universal')
            **params: Route parameters (e.g., product_id, order_id)
        
        Returns:
            Complete deep link URL
        """
        if route not in cls.DEEP_LINK_ROUTES:
            logger.warning(f"Unknown deep link route: {route}")
            return cls.APP_SCHEMES.get(platform, cls.APP_SCHEMES['universal'])
        
        # Get the route template
        route_template = cls.DEEP_LINK_ROUTES[route]
        
        # Replace parameters in the route
        try:
            formatted_route = route_template.format(**params)
        except KeyError as e:
            logger.error(f"Missing parameter for deep link route {route}: {e}")
            formatted_route = route_template
        
        # Construct the full deep link
        base_scheme = cls.APP_SCHEMES.get(platform, cls.APP_SCHEMES['universal'])
        deep_link = f"{base_scheme}{formatted_route}"
        
        # Add query parameters if any
        query_params = {k: v for k, v in params.items() 
                       if f"{{{k}}}" not in route_template}
        
        if query_params:
            query_string = urllib.parse.urlencode(query_params)
            deep_link = f"{deep_link}?{query_string}"
        
        return deep_link
    
    @classmethod
    def generate_smart_link(cls, route: str, fallback_url: str = None, **params) -> Dict[str, str]:
        """
        Generate smart links for all platforms with fallback URLs.
        
        Args:
            route: The route key from DEEP_LINK_ROUTES
            fallback_url: Web URL to use as fallback
            **params: Route parameters
        
        Returns:
            Dictionary with platform-specific links and fallback
        """
        links = {}
        
        for platform in ['ios', 'android', 'universal']:
            links[platform] = cls.generate_deep_link(route, platform, **params)
        
        if fallback_url:
            links['fallback'] = fallback_url
        
        return links
    
    @classmethod
    def create_universal_link_html(cls, route: str, fallback_url: str, 
                                 link_text: str = "Open in App", **params) -> str:
        """
        Create HTML for a universal link that attempts to open the app
        and falls back to the web URL.
        
        Args:
            route: The route key from DEEP_LINK_ROUTES
            fallback_url: Web URL to use as fallback
            link_text: Text to display for the link
            **params: Route parameters
        
        Returns:
            HTML string for the universal link
        """
        deep_link = cls.generate_deep_link(route, 'universal', **params)
        
        html = f'''
        <a href="{deep_link}" 
           onclick="setTimeout(function(){{window.location='{fallback_url}';}}, 1000);"
           class="deep-link-button">
            {link_text}
        </a>
        '''
        
        return html.strip()


class DeepLinkHandler:
    """
    Handles incoming deep link requests and redirects appropriately.
    """
    
    @staticmethod
    def handle_deep_link_redirect(request, route: str, **params):
        """
        Handle deep link redirect based on user agent and preferences.
        
        Args:
            request: Django request object
            route: The route to redirect to
            **params: Route parameters
        
        Returns:
            HttpResponseRedirect to appropriate URL
        """
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        # Check if request is from mobile app
        if 'findmytaste' in user_agent:
            # Request is already from the app, redirect to web version
            web_url = DeepLinkHandler._get_web_url(route, **params)
            return HttpResponseRedirect(web_url)
        
        # Check if user prefers app or has app installed
        prefer_app = request.GET.get('prefer_app', 'true').lower() == 'true'
        
        if prefer_app:
            # Detect platform and generate appropriate deep link
            if 'iphone' in user_agent or 'ipad' in user_agent:
                platform = 'ios'
            elif 'android' in user_agent:
                platform = 'android'
            else:
                platform = 'universal'
            
            deep_link = DeepLinkManager.generate_deep_link(route, platform, **params)
            
            # Create a redirect page that attempts app launch
            return DeepLinkHandler._create_app_launch_page(
                request, deep_link, route, **params
            )
        else:
            # Redirect to web version
            web_url = DeepLinkHandler._get_web_url(route, **params)
            return HttpResponseRedirect(web_url)
    
    @staticmethod
    def _get_web_url(route: str, **params) -> str:
        """
        Get the corresponding web URL for a deep link route.
        """
        # Map deep link routes to Django URL names
        route_mapping = {
            'login': 'login',
            'register': 'buyer-register',
            'product_detail': 'product-detail',
            'order_detail': 'order-detail',
            # Add more mappings as needed
        }
        
        url_name = route_mapping.get(route)
        if url_name:
            try:
                return reverse(url_name, kwargs=params)
            except:
                pass
        
        # Fallback to home page
        return '/'
    
    @staticmethod
    def _create_app_launch_page(request, deep_link: str, route: str, **params):
        """
        Create a page that attempts to launch the app and provides fallback.
        """
        from django.template.response import TemplateResponse
        
        web_url = DeepLinkHandler._get_web_url(route, **params)
        
        context = {
            'deep_link': deep_link,
            'web_url': web_url,
            'route': route,
            'params': params
        }
        
        return TemplateResponse(request, 'deep_link_redirect.html', context)


# Utility functions for common deep link scenarios
def generate_product_deep_link(product_id: str, platform: str = 'universal') -> str:
    """Generate deep link for product detail page."""
    return DeepLinkManager.generate_deep_link('product_detail', platform, product_id=product_id)

def generate_order_deep_link(order_id: str, platform: str = 'universal') -> str:
    """Generate deep link for order detail page."""
    return DeepLinkManager.generate_deep_link('order_detail', platform, order_id=order_id)

def generate_vendor_deep_link(vendor_id: str, platform: str = 'universal') -> str:
    """Generate deep link for vendor profile page."""
    return DeepLinkManager.generate_deep_link('vendor_profile', platform, vendor_id=vendor_id)

def generate_auth_deep_link(auth_type: str = 'login', platform: str = 'universal', **params) -> str:
    """Generate deep link for authentication pages."""
    return DeepLinkManager.generate_deep_link(auth_type, platform, **params)