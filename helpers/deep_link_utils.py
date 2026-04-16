"""
Deep Link Utilities for FindMyTaste App

Utility functions for deep link analytics, QR code generation,
mobile detection, and other deep linking related functionality.
"""

import qrcode
import base64
from io import BytesIO
from urllib.parse import urlencode, urlparse, parse_qs
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse
import json
import hashlib
import re


class DeepLinkAnalytics:
    """
    Analytics tracking for deep link usage and performance.
    """
    
    @staticmethod
    def track_deep_link_click(request, route, params=None):
        """
        Track when a deep link is clicked.
        """
        try:
            analytics_data = {
                'route': route,
                'params': params or {},
                'timestamp': timezone.now().isoformat(),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip_address': DeepLinkAnalytics._get_client_ip(request),
                'referrer': request.META.get('HTTP_REFERER', ''),
                'platform': DeepLinkAnalytics._detect_platform(request),
                'session_id': request.session.session_key,
            }
            
            # Store in cache for real-time analytics
            cache_key = f"deep_link_click_{timezone.now().strftime('%Y%m%d_%H')}"
            clicks = cache.get(cache_key, [])
            clicks.append(analytics_data)
            cache.set(cache_key, clicks, timeout=3600)  # 1 hour
            
            # You might want to also store in database for long-term analytics
            # DeepLinkClick.objects.create(**analytics_data)
            
        except Exception as e:
            # Log error but don't break the flow
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking deep link click: {e}")
    
    @staticmethod
    def track_app_install(request, source_route=None):
        """
        Track when the app is installed from a deep link.
        """
        try:
            install_data = {
                'source_route': source_route,
                'timestamp': timezone.now().isoformat(),
                'platform': DeepLinkAnalytics._detect_platform(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip_address': DeepLinkAnalytics._get_client_ip(request),
            }
            
            cache_key = f"app_install_{timezone.now().strftime('%Y%m%d')}"
            installs = cache.get(cache_key, [])
            installs.append(install_data)
            cache.set(cache_key, installs, timeout=86400)  # 24 hours
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking app install: {e}")
    
    @staticmethod
    def get_analytics_summary(date_range=7):
        """
        Get analytics summary for the specified date range.
        """
        try:
            summary = {
                'total_clicks': 0,
                'total_installs': 0,
                'popular_routes': {},
                'platform_breakdown': {},
                'conversion_rate': 0,
            }
            
            # This is a simplified version using cache
            # In production, you'd query your database
            
            return summary
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting analytics summary: {e}")
            return {}
    
    @staticmethod
    def _get_client_ip(request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def _detect_platform(request):
        """Detect the user's platform."""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'iphone' in user_agent or 'ipad' in user_agent:
            return 'ios'
        elif 'android' in user_agent:
            return 'android'
        elif 'windows phone' in user_agent:
            return 'windows_phone'
        else:
            return 'unknown'


class QRCodeGenerator:
    """
    Generate QR codes for deep links.
    """
    
    @staticmethod
    def generate_qr_code(url, size='medium', format='png'):
        """
        Generate a QR code for the given URL.
        
        Args:
            url (str): The URL to encode
            size (str): Size of QR code ('small', 'medium', 'large')
            format (str): Output format ('png', 'svg', 'base64')
        
        Returns:
            BytesIO or str: QR code data
        """
        try:
            # Size mapping
            size_map = {
                'small': 5,
                'medium': 10,
                'large': 15
            }
            
            box_size = size_map.get(size, 10)
            
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=box_size,
                border=4,
            )
            
            qr.add_data(url)
            qr.make(fit=True)
            
            if format == 'svg':
                # Generate SVG
                from qrcode.image.svg import SvgPathImage
                img = qr.make_image(image_factory=SvgPathImage)
                svg_buffer = BytesIO()
                img.save(svg_buffer)
                return svg_buffer.getvalue().decode('utf-8')
            
            else:
                # Generate PNG
                img = qr.make_image(fill_color="black", back_color="white")
                img_buffer = BytesIO()
                img.save(img_buffer, format='PNG')
                
                if format == 'base64':
                    img_buffer.seek(0)
                    img_data = base64.b64encode(img_buffer.getvalue()).decode()
                    return f"data:image/png;base64,{img_data}"
                else:
                    img_buffer.seek(0)
                    return img_buffer
                    
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating QR code: {e}")
            return None
    
    @staticmethod
    def generate_branded_qr_code(url, logo_path=None, brand_color='#667eea'):
        """
        Generate a branded QR code with logo and custom colors.
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,  # Higher error correction for logo
                box_size=10,
                border=4,
            )
            
            qr.add_data(url)
            qr.make(fit=True)
            
            # Create image with custom colors
            img = qr.make_image(fill_color=brand_color, back_color="white")
            
            # Add logo if provided
            if logo_path:
                try:
                    from PIL import Image
                    logo = Image.open(logo_path)
                    
                    # Calculate logo size (10% of QR code)
                    qr_width, qr_height = img.size
                    logo_size = min(qr_width, qr_height) // 10
                    
                    # Resize logo
                    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    
                    # Calculate position (center)
                    logo_pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
                    
                    # Paste logo
                    img.paste(logo, logo_pos)
                    
                except Exception as logo_error:
                    # Continue without logo if there's an error
                    pass
            
            img_buffer = BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            return img_buffer
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating branded QR code: {e}")
            return None


class MobileDetection:
    """
    Advanced mobile device and app detection utilities.
    """
    
    # Comprehensive mobile user agent patterns
    MOBILE_PATTERNS = [
        r'Mobile', r'Android', r'iPhone', r'iPad', r'iPod',
        r'BlackBerry', r'Windows Phone', r'Opera Mini',
        r'IEMobile', r'Mobile Safari', r'webOS', r'Kindle'
    ]
    
    # Tablet-specific patterns
    TABLET_PATTERNS = [
        r'iPad', r'Android.*Tablet', r'Kindle', r'Silk',
        r'PlayBook', r'Tablet'
    ]
    
    # App-specific patterns
    APP_PATTERNS = [
        r'FindMyTaste', r'findmytaste'
    ]
    
    @classmethod
    def is_mobile(cls, request):
        """Check if the request is from a mobile device."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return any(re.search(pattern, user_agent, re.IGNORECASE) 
                  for pattern in cls.MOBILE_PATTERNS)
    
    @classmethod
    def is_tablet(cls, request):
        """Check if the request is from a tablet."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return any(re.search(pattern, user_agent, re.IGNORECASE) 
                  for pattern in cls.TABLET_PATTERNS)
    
    @classmethod
    def is_app(cls, request):
        """Check if the request is from the mobile app."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check user agent
        if any(re.search(pattern, user_agent, re.IGNORECASE) 
               for pattern in cls.APP_PATTERNS):
            return True
        
        # Check custom headers
        if request.META.get('HTTP_X_FINDMYTASTE_APP'):
            return True
        
        return False
    
    @classmethod
    def get_platform(cls, request):
        """Get the platform (ios, android, web)."""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'iphone' in user_agent or 'ipad' in user_agent:
            return 'ios'
        elif 'android' in user_agent:
            return 'android'
        elif 'windows phone' in user_agent:
            return 'windows_phone'
        else:
            return 'web'
    
    @classmethod
    def get_device_info(cls, request):
        """Get detailed device information."""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return {
            'is_mobile': cls.is_mobile(request),
            'is_tablet': cls.is_tablet(request),
            'is_app': cls.is_app(request),
            'platform': cls.get_platform(request),
            'user_agent': user_agent,
            'supports_deep_links': cls.supports_deep_links(request),
        }
    
    @classmethod
    def supports_deep_links(cls, request):
        """Check if the device supports deep links."""
        platform = cls.get_platform(request)
        return platform in ['ios', 'android']


class ShareLinkGenerator:
    """
    Generate shareable links with metadata and tracking.
    """
    
    @staticmethod
    def generate_share_link(route, params=None, title=None, description=None, image_url=None):
        """
        Generate a shareable link with metadata.
        """
        try:
            from django.urls import reverse
            
            # Generate base deep link URL
            base_url = reverse('deep_links:share_link', kwargs={'route': route})
            
            # Add parameters
            query_params = {}
            if params:
                query_params.update(params)
            
            # Add metadata
            if title:
                query_params['title'] = title
            if description:
                query_params['description'] = description
            if image_url:
                query_params['image'] = image_url
            
            # Add tracking ID
            tracking_id = ShareLinkGenerator._generate_tracking_id(route, params)
            query_params['t'] = tracking_id
            
            if query_params:
                base_url += '?' + urlencode(query_params)
            
            return base_url
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating share link: {e}")
            return None
    
    @staticmethod
    def _generate_tracking_id(route, params):
        """Generate a unique tracking ID for the share link."""
        data = f"{route}_{params}_{timezone.now().timestamp()}"
        return hashlib.md5(data.encode()).hexdigest()[:8]
    
    @staticmethod
    def track_share_link_click(tracking_id, request):
        """Track when a share link is clicked."""
        try:
            click_data = {
                'tracking_id': tracking_id,
                'timestamp': timezone.now().isoformat(),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip_address': DeepLinkAnalytics._get_client_ip(request),
                'referrer': request.META.get('HTTP_REFERER', ''),
            }
            
            cache_key = f"share_click_{tracking_id}"
            clicks = cache.get(cache_key, [])
            clicks.append(click_data)
            cache.set(cache_key, clicks, timeout=86400 * 30)  # 30 days
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking share link click: {e}")


class UniversalLinkValidator:
    """
    Validate and process Universal Links (iOS) and App Links (Android).
    """
    
    @staticmethod
    def validate_universal_link(request):
        """
        Validate if the request is a valid Universal Link.
        """
        # Check for Apple's validation
        if request.path == '/apple-app-site-association':
            return True
        
        # Check for Android's validation
        if request.path == '/.well-known/assetlinks.json':
            return True
        
        return False
    
    @staticmethod
    def generate_apple_app_site_association():
        """
        Generate Apple App Site Association file.
        """
        association = {
            "applinks": {
                "apps": [],
                "details": [
                    {
                        "appID": getattr(settings, 'IOS_APP_ID', 'TEAMID.com.findmytaste.app'),
                        "paths": [
                            "/dl/*",
                            "/app/*",
                            "/share/*"
                        ]
                    }
                ]
            }
        }
        
        return JsonResponse(association)
    
    @staticmethod
    def generate_android_asset_links():
        """
        Generate Android Asset Links file.
        """
        asset_links = [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": getattr(settings, 'ANDROID_PACKAGE_NAME', 'com.findmytaste.app'),
                    "sha256_cert_fingerprints": [
                        getattr(settings, 'ANDROID_CERT_FINGERPRINT', '')
                    ]
                }
            }
        ]
        
        return JsonResponse(asset_links, safe=False)


def create_deep_link_response(request, route, params=None, fallback_url=None):
    """
    Create a standardized deep link response.
    """
    from .deep_linking import DeepLinkManager
    
    try:
        # Track the click
        DeepLinkAnalytics.track_deep_link_click(request, route, params)
        
        # Generate deep link
        manager = DeepLinkManager()
        deep_link = manager.generate_deep_link(route, params or {})
        
        # Get device info
        device_info = MobileDetection.get_device_info(request)
        
        # Prepare response data
        response_data = {
            'deep_link': deep_link,
            'fallback_url': fallback_url or '/',
            'device_info': device_info,
            'route': route,
            'params': params or {},
        }
        
        return response_data
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating deep link response: {e}")
        
        return {
            'deep_link': None,
            'fallback_url': fallback_url or '/',
            'error': str(e)
        }