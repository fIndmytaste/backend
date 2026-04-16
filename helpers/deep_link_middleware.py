"""
Deep Link Middleware for FindMyTaste App

This middleware automatically detects mobile users and provides
smart app redirects and deep linking functionality.
"""

import re
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from .deep_linking import DeepLinkManager


class DeepLinkMiddleware(MiddlewareMixin):
    """
    Middleware to handle automatic deep link redirects for mobile users.
    """
    
    # Mobile user agent patterns
    MOBILE_USER_AGENTS = [
        r'Mobile', r'Android', r'iPhone', r'iPad', r'iPod',
        r'BlackBerry', r'Windows Phone', r'Opera Mini'
    ]
    
    # Routes that should trigger app redirects
    APP_REDIRECT_ROUTES = [
        r'^/api/v1/products/\d+/$',
        r'^/api/v1/vendor/\d+/$',
        r'^/api/v1/order/\d+/$',
        r'^/api/v1/auth/login/$',
        r'^/api/v1/auth/register/$',
    ]
    
    # Routes to exclude from app redirects
    EXCLUDE_ROUTES = [
        r'^/admin/',
        r'^/swagger/',
        r'^/dl/',  # Already deep link routes
        r'^/app/',  # Universal link routes
        r'^/download/',  # App download routes
        r'^/api/v1/.*\.(json|xml)$',  # API responses
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
        
        # Compile regex patterns for performance
        self.mobile_patterns = [re.compile(pattern, re.IGNORECASE) 
                               for pattern in self.MOBILE_USER_AGENTS]
        self.redirect_patterns = [re.compile(pattern) 
                                 for pattern in self.APP_REDIRECT_ROUTES]
        self.exclude_patterns = [re.compile(pattern) 
                                for pattern in self.EXCLUDE_ROUTES]
    
    def process_request(self, request):
        """
        Process incoming requests for deep link opportunities.
        """
        # Skip if deep linking is disabled
        if not getattr(settings, 'ENABLE_DEEP_LINKING', True):
            return None
        
        # Skip for non-GET requests
        if request.method != 'GET':
            return None
        
        # Skip if user explicitly disabled app redirects
        if request.GET.get('no_app_redirect') == 'true':
            return None
        
        # Skip if already in app (detected by custom header or user agent)
        if self._is_app_request(request):
            return None
        
        # Check if route should be excluded
        if self._should_exclude_route(request.path):
            return None
        
        # Check if this is a mobile user
        if not self._is_mobile_user(request):
            return None
        
        # Check if route should trigger app redirect
        deep_link_route = self._get_deep_link_route(request)
        if deep_link_route:
            return self._create_app_redirect(request, deep_link_route)
        
        return None
    
    def _is_mobile_user(self, request):
        """Check if the user is on a mobile device."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return any(pattern.search(user_agent) for pattern in self.mobile_patterns)
    
    def _is_app_request(self, request):
        """Check if the request is coming from the mobile app."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check for custom app identifier in user agent
        if 'FindMyTaste' in user_agent or 'findmytaste' in user_agent.lower():
            return True
        
        # Check for custom header
        if request.META.get('HTTP_X_FINDMYTASTE_APP'):
            return True
        
        return False
    
    def _should_exclude_route(self, path):
        """Check if the route should be excluded from app redirects."""
        return any(pattern.match(path) for pattern in self.exclude_patterns)
    
    def _get_deep_link_route(self, request):
        """
        Determine the appropriate deep link route for the current request.
        """
        path = request.path
        
        # Map common web routes to deep link routes
        route_mappings = {
            r'^/api/v1/auth/login/$': ('login', {}),
            r'^/api/v1/auth/buyer-register/$': ('register', {}),
            r'^/api/v1/auth/vendor-register/$': ('register', {'type': 'vendor'}),
            r'^/api/v1/auth/rider-register/$': ('register', {'type': 'rider'}),
            r'^/api/v1/products/(\d+)/$': ('product_detail', lambda m: {'product_id': m.group(1)}),
            r'^/api/v1/vendor/(\d+)/$': ('vendor_profile', lambda m: {'vendor_id': m.group(1)}),
            r'^/api/v1/orders/(\d+)/$': ('order_detail', lambda m: {'order_id': m.group(1)}),
            r'^/api/v1/marketplace/$': ('marketplace', {}),
            r'^/api/v1/wallet/$': ('wallet', {}),
        }
        
        for pattern, (route, params_func) in route_mappings.items():
            match = re.match(pattern, path)
            if match:
                if callable(params_func):
                    params = params_func(match)
                else:
                    params = params_func
                
                # Add query parameters
                for key, value in request.GET.items():
                    if key not in ['prefer_app', 'platform', 'no_app_redirect']:
                        params[key] = value
                
                return route, params
        
        return None
    
    def _create_app_redirect(self, request, deep_link_data):
        """
        Create a redirect response to the app or deep link page.
        """
        route, params = deep_link_data
        
        # Check user preference for app redirects
        prefer_app = request.COOKIES.get('prefer_app', 'true') == 'true'
        
        if not prefer_app:
            return None
        
        # Build deep link redirect URL
        try:
            redirect_url = reverse('deep_links:deep_link_redirect', kwargs={'route': route})
            
            # Add parameters as query string
            if params:
                query_params = []
                for key, value in params.items():
                    query_params.append(f"{key}={value}")
                
                if query_params:
                    redirect_url += '?' + '&'.join(query_params)
            
            return HttpResponseRedirect(redirect_url)
        
        except Exception as e:
            # Log error and continue with normal request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating deep link redirect: {e}")
            return None


class SmartBannerMiddleware(MiddlewareMixin):
    """
    Middleware to inject smart app banners for mobile web users.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """
        Inject smart banner HTML into responses for mobile users.
        """
        # Skip if smart banners are disabled
        if not getattr(settings, 'ENABLE_SMART_BANNERS', True):
            return response
        
        # Only process HTML responses
        if not response.get('Content-Type', '').startswith('text/html'):
            return response
        
        # Skip if user is already in app
        if self._is_app_request(request):
            return response
        
        # Skip if user dismissed banner
        if request.COOKIES.get('banner_dismissed') == 'true':
            return response
        
        # Check if this is a mobile user
        if not self._is_mobile_user(request):
            return response
        
        # Inject smart banner
        banner_html = self._get_smart_banner_html(request)
        if banner_html:
            response.content = self._inject_banner(response.content, banner_html)
        
        return response
    
    def _is_mobile_user(self, request):
        """Check if the user is on a mobile device."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        mobile_patterns = [
            r'Mobile', r'Android', r'iPhone', r'iPad', r'iPod',
            r'BlackBerry', r'Windows Phone', r'Opera Mini'
        ]
        return any(re.search(pattern, user_agent, re.IGNORECASE) 
                  for pattern in mobile_patterns)
    
    def _is_app_request(self, request):
        """Check if the request is coming from the mobile app."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return 'FindMyTaste' in user_agent or 'findmytaste' in user_agent.lower()
    
    def _get_smart_banner_html(self, request):
        """Generate smart banner HTML."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Determine platform
        if 'iPhone' in user_agent or 'iPad' in user_agent:
            platform = 'ios'
            store_url = reverse('deep_links:ios_download')
        elif 'Android' in user_agent:
            platform = 'android'
            store_url = reverse('deep_links:android_download')
        else:
            return None
        
        # Get current page deep link
        current_route = self._get_current_route(request)
        if current_route:
            deep_link_url = reverse('deep_links:deep_link_redirect', 
                                  kwargs={'route': current_route})
        else:
            deep_link_url = reverse('deep_links:deep_link_redirect', 
                                  kwargs={'route': 'marketplace'})
        
        banner_html = f'''
        <div id="smart-banner" style="
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            padding: 10px 15px;
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
        ">
            <div style="display: flex; align-items: center;">
                <div style="
                    width: 40px;
                    height: 40px;
                    background: #667eea;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-right: 12px;
                    font-size: 20px;
                ">🍽️</div>
                <div>
                    <div style="font-weight: 600; color: #333;">FindMyTaste</div>
                    <div style="color: #666; font-size: 12px;">Get the app for the best experience</div>
                </div>
            </div>
            <div style="display: flex; gap: 8px;">
                <a href="{deep_link_url}" style="
                    background: #667eea;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                    text-decoration: none;
                    font-weight: 500;
                    font-size: 12px;
                ">OPEN</a>
                <button onclick="document.getElementById('smart-banner').style.display='none'; 
                               document.cookie='banner_dismissed=true; max-age=86400';" style="
                    background: none;
                    border: none;
                    color: #666;
                    font-size: 18px;
                    cursor: pointer;
                    padding: 0;
                    width: 24px;
                    height: 24px;
                ">×</button>
            </div>
        </div>
        <script>
            // Add top margin to body to account for banner
            document.body.style.marginTop = '70px';
        </script>
        '''
        
        return banner_html
    
    def _get_current_route(self, request):
        """Get the current route for deep linking."""
        # This is a simplified version - you might want to implement
        # more sophisticated route detection based on your URL patterns
        path = request.path
        
        if '/products/' in path:
            return 'marketplace'
        elif '/auth/' in path:
            return 'login'
        elif '/orders/' in path:
            return 'order_history'
        
        return 'marketplace'
    
    def _inject_banner(self, content, banner_html):
        """Inject banner HTML into the response content."""
        try:
            content_str = content.decode('utf-8')
            
            # Find the opening body tag and inject banner after it
            body_start = content_str.find('<body')
            if body_start != -1:
                body_end = content_str.find('>', body_start) + 1
                content_str = (content_str[:body_end] + 
                             banner_html + 
                             content_str[body_end:])
                return content_str.encode('utf-8')
        except:
            pass
        
        return content