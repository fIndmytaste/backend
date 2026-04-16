"""
Deep Link Views for FindMyTaste App

This module contains view classes that handle deep link redirects
and mobile app integration.
"""

import json
import qrcode
import io
import base64
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.views.generic import View
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .deep_linking import DeepLinkManager, DeepLinkHandler
from account.models import User
from product.models import Order
from account.models import Vendor


class BaseDeepLinkView(View):
    """
    Base view for handling deep link redirects.
    """
    route_name = None
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests for deep links."""
        # Extract parameters from URL and query string
        params = self.get_route_params(request, *args, **kwargs)
        
        # Handle the deep link redirect
        return DeepLinkHandler.handle_deep_link_redirect(
            request, self.route_name, **params
        )
    
    def get_route_params(self, request, *args, **kwargs):
        """Extract route parameters from the request."""
        params = kwargs.copy()
        
        # Add query parameters
        for key, value in request.GET.items():
            if key not in ['prefer_app', 'platform']:
                params[key] = value
        
        return params


class DeepLinkRedirectView(BaseDeepLinkView):
    """
    Generic deep link redirect view.
    """
    
    def get(self, request, route, *args, **kwargs):
        self.route_name = route
        return super().get(request, *args, **kwargs)


class AuthDeepLinkView(BaseDeepLinkView):
    """
    Handle authentication-related deep links.
    """
    
    def get(self, request, auth_type, *args, **kwargs):
        self.route_name = auth_type
        
        # Add authentication-specific parameters
        params = self.get_route_params(request, *args, **kwargs)
        
        # Handle email verification links
        if auth_type == 'verify_account':
            email = request.GET.get('email')
            code = request.GET.get('code')
            if email and code:
                params.update({'email': email, 'code': code})
        
        # Handle password reset links
        elif auth_type == 'reset_password':
            token = request.GET.get('token')
            uid = request.GET.get('uid')
            if token and uid:
                params.update({'token': token, 'uid': uid})
        
        return DeepLinkHandler.handle_deep_link_redirect(
            request, self.route_name, **params
        )


class ProductDeepLinkView(BaseDeepLinkView):
    """
    Handle product-related deep links.
    """
    route_name = 'product_detail'
    
    def get_route_params(self, request, product_id, *args, **kwargs):
        params = super().get_route_params(request, *args, **kwargs)
        params['product_id'] = product_id
        return params


class CategoryDeepLinkView(BaseDeepLinkView):
    """
    Handle category-related deep links.
    """
    route_name = 'category'
    
    def get_route_params(self, request, category_id, *args, **kwargs):
        params = super().get_route_params(request, *args, **kwargs)
        params['category_id'] = category_id
        return params


class VendorDeepLinkView(BaseDeepLinkView):
    """
    Handle vendor profile deep links.
    """
    route_name = 'vendor_profile'
    
    def get_route_params(self, request, vendor_id, *args, **kwargs):
        params = super().get_route_params(request, *args, **kwargs)
        params['vendor_id'] = vendor_id
        return params


class OrderDeepLinkView(BaseDeepLinkView):
    """
    Handle order-related deep links.
    """
    route_name = 'order_detail'
    
    def get_route_params(self, request, order_id, *args, **kwargs):
        params = super().get_route_params(request, *args, **kwargs)
        params['order_id'] = order_id
        return params


class OrderTrackingDeepLinkView(BaseDeepLinkView):
    """
    Handle order tracking deep links.
    """
    route_name = 'order_tracking'
    
    def get_route_params(self, request, order_id, *args, **kwargs):
        params = super().get_route_params(request, *args, **kwargs)
        params['order_id'] = order_id
        return params


class ProfileDeepLinkView(BaseDeepLinkView):
    """
    Handle user profile deep links.
    """
    route_name = 'profile'


class WalletDeepLinkView(BaseDeepLinkView):
    """
    Handle wallet deep links.
    """
    route_name = 'wallet'


class RiderDashboardDeepLinkView(BaseDeepLinkView):
    """
    Handle rider dashboard deep links.
    """
    route_name = 'rider_dashboard'


class RiderOrderDeepLinkView(BaseDeepLinkView):
    """
    Handle rider order detail deep links.
    """
    route_name = 'rider_order_detail'
    
    def get_route_params(self, request, order_id, *args, **kwargs):
        params = super().get_route_params(request, *args, **kwargs)
        params['order_id'] = order_id
        return params


class VendorDashboardDeepLinkView(BaseDeepLinkView):
    """
    Handle vendor dashboard deep links.
    """
    route_name = 'vendor_dashboard'


class MarketplaceDeepLinkView(BaseDeepLinkView):
    """
    Handle marketplace deep links.
    """
    route_name = 'marketplace'


class NotificationDeepLinkView(BaseDeepLinkView):
    """
    Handle notification deep links.
    """
    route_name = 'notifications'


class UniversalLinkView(View):
    """
    Handle iOS Universal Links.
    """
    
    def get(self, request, route, *args, **kwargs):
        """Handle universal link requests."""
        # Extract parameters
        params = kwargs.copy()
        for key, value in request.GET.items():
            params[key] = value
        
        # Generate appropriate deep link
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'iphone' in user_agent or 'ipad' in user_agent:
            platform = 'ios'
        elif 'android' in user_agent:
            platform = 'android'
        else:
            platform = 'universal'
        
        deep_link = DeepLinkManager.generate_deep_link(route, platform, **params)
        
        # Return JSON response for app consumption or redirect for web
        if request.GET.get('format') == 'json':
            return JsonResponse({
                'deep_link': deep_link,
                'route': route,
                'params': params,
                'platform': platform
            })
        
        return HttpResponseRedirect(deep_link)


class AppDownloadView(View):
    """
    Handle app download redirects.
    """
    
    def get(self, request, platform=None, *args, **kwargs):
        """Redirect to appropriate app store."""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        # Auto-detect platform if not specified
        if not platform:
            if 'iphone' in user_agent or 'ipad' in user_agent:
                platform = 'ios'
            elif 'android' in user_agent:
                platform = 'android'
            else:
                platform = 'web'
        
        # App store URLs (replace with actual URLs)
        store_urls = {
            'ios': 'https://apps.apple.com/app/findmytaste/id123456789',
            'android': 'https://play.google.com/store/apps/details?id=com.findmytaste.app',
            'web': '/'  # Fallback to web app
        }
        
        download_url = store_urls.get(platform, store_urls['web'])
        return HttpResponseRedirect(download_url)


class QRCodeView(View):
    """
    Generate QR codes for deep links.
    """
    
    def get(self, request, route, *args, **kwargs):
        """Generate QR code for a deep link."""
        # Extract parameters
        params = kwargs.copy()
        for key, value in request.GET.items():
            if key not in ['size', 'format']:
                params[key] = value
        
        # Generate deep link
        deep_link = DeepLinkManager.generate_deep_link(route, 'universal', **params)
        
        # QR code settings
        size = int(request.GET.get('size', 200))
        qr_format = request.GET.get('format', 'png').lower()
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(deep_link)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size, size))
        
        # Return image response
        if qr_format == 'svg':
            # SVG format
            import qrcode.image.svg
            factory = qrcode.image.svg.SvgPathImage
            img = qrcode.make(deep_link, image_factory=factory)
            response = HttpResponse(content_type='image/svg+xml')
            img.save(response)
        else:
            # PNG format
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            response = HttpResponse(buffer.getvalue(), content_type='image/png')
        
        return response


class ShareLinkView(APIView):
    """
    Generate shareable links with metadata.
    """
    
    def get(self, request, route, *args, **kwargs):
        """Generate shareable link with metadata."""
        # Extract parameters
        params = kwargs.copy()
        for key, value in request.GET.items():
            params[key] = value
        
        # Generate links for all platforms
        links = DeepLinkManager.generate_smart_link(route, **params)
        
        # Add metadata based on route type
        metadata = self.get_route_metadata(route, **params)
        
        # Generate QR code URL
        qr_url = request.build_absolute_uri(
            reverse('deep_links:qr_code', kwargs={'route': route})
        )
        if params:
            qr_url += '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        response_data = {
            'links': links,
            'metadata': metadata,
            'qr_code_url': qr_url,
            'share_url': request.build_absolute_uri(),
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    def get_route_metadata(self, route, **params):
        """Get metadata for the route."""
        metadata = {
            'title': 'FindMyTaste',
            'description': 'Discover amazing food and restaurants',
            'image': None,
        }
        
        # Customize metadata based on route
        if route == 'product_detail':
            metadata.update({
                'title': f'Product - FindMyTaste',
                'description': 'Check out this amazing product on FindMyTaste',
            })
        elif route == 'vendor_profile':
            metadata.update({
                'title': f'Restaurant - FindMyTaste',
                'description': 'Discover this restaurant on FindMyTaste',
            })
        elif route == 'order_detail':
            metadata.update({
                'title': f'Order Details - FindMyTaste',
                'description': 'View your order details on FindMyTaste',
            })
        
        return metadata


class MobileAppBridgeView(View):
    """
    Mobile app bridge page for testing deep linking functionality.
    """
    template_name = 'deep_link/mobile_app_bridge.html'
    
    def get(self, request):
        context = {
            'app_name': getattr(settings, 'APP_NAME', 'FindMyTaste'),
            'app_description': getattr(settings, 'APP_DESCRIPTION', 'Discover amazing food with FindMyTaste'),
            'ios_app_store_url': getattr(settings, 'IOS_APP_STORE_URL', ''),
            'android_play_store_url': getattr(settings, 'ANDROID_PLAY_STORE_URL', ''),
            'enable_smart_banner': getattr(settings, 'ENABLE_SMART_BANNERS', True),
            'enable_auto_redirect': getattr(settings, 'ENABLE_AUTO_REDIRECT', True),
        }
        
        return render(request, self.template_name, context)


@method_decorator(csrf_exempt, name='dispatch')
class DeepLinkAnalyticsView(APIView):
    """
    Track deep link analytics and usage.
    """
    
    def post(self, request):
        """Log deep link usage analytics."""
        data = request.data
        
        # Extract analytics data
        route = data.get('route')
        platform = data.get('platform')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = request.META.get('REMOTE_ADDR', '')
        
        # Log analytics (implement your logging logic here)
        # This could be saved to database, sent to analytics service, etc.
        
        return Response({'status': 'logged'}, status=status.HTTP_200_OK)