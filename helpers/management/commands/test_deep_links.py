"""
Django management command to test deep linking functionality.

Usage:
    python manage.py test_deep_links
    python manage.py test_deep_links --route marketplace
    python manage.py test_deep_links --generate-qr
    python manage.py test_deep_links --analytics
"""

from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory
from django.conf import settings
import json
from helpers.deep_linking import DeepLinkManager, DeepLinkHandler
from helpers.deep_link_utils import (
    QRCodeGenerator, 
    MobileDetection, 
    DeepLinkAnalytics,
    ShareLinkGenerator
)


class Command(BaseCommand):
    help = 'Test deep linking functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--route',
            type=str,
            help='Test specific route (e.g., marketplace, product_detail)',
        )
        
        parser.add_argument(
            '--params',
            type=str,
            help='JSON string of parameters for the route',
        )
        
        parser.add_argument(
            '--generate-qr',
            action='store_true',
            help='Generate QR codes for all routes',
        )
        
        parser.add_argument(
            '--analytics',
            action='store_true',
            help='Show analytics summary',
        )
        
        parser.add_argument(
            '--validate-config',
            action='store_true',
            help='Validate deep linking configuration',
        )
        
        parser.add_argument(
            '--test-mobile-detection',
            action='store_true',
            help='Test mobile device detection',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔗 Testing Deep Linking Functionality\n')
        )
        
        try:
            if options['validate_config']:
                self.validate_configuration()
            
            if options['test_mobile_detection']:
                self.test_mobile_detection()
            
            if options['route']:
                self.test_specific_route(options['route'], options.get('params'))
            
            if options['generate_qr']:
                self.generate_qr_codes()
            
            if options['analytics']:
                self.show_analytics()
            
            if not any([options['route'], options['generate_qr'], 
                       options['analytics'], options['validate_config'],
                       options['test_mobile_detection']]):
                self.run_comprehensive_test()
                
        except Exception as e:
            raise CommandError(f'Error testing deep links: {e}')
    
    def validate_configuration(self):
        """Validate deep linking configuration."""
        self.stdout.write('📋 Validating Configuration...\n')
        
        # Check required settings
        required_settings = [
            'IOS_URL_SCHEME',
            'ANDROID_URL_SCHEME',
            'IOS_APP_STORE_URL',
            'ANDROID_PLAY_STORE_URL'
        ]
        
        missing_settings = []
        for setting in required_settings:
            if not getattr(settings, setting, None):
                missing_settings.append(setting)
        
        if missing_settings:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  Missing settings: {", ".join(missing_settings)}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ All required settings are configured')
            )
        
        # Check supported routes
        supported_routes = getattr(settings, 'SUPPORTED_ROUTES', {})
        self.stdout.write(f'📱 Supported routes: {len(supported_routes)}')
        
        for route, config in supported_routes.items():
            self.stdout.write(f'  • {route}: {config.get("title", "No title")}')
        
        self.stdout.write('')
    
    def test_mobile_detection(self):
        """Test mobile device detection."""
        self.stdout.write('📱 Testing Mobile Detection...\n')
        
        # Create test requests with different user agents
        test_cases = [
            ('iPhone', 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'),
            ('Android', 'Mozilla/5.0 (Linux; Android 10; SM-G975F)'),
            ('iPad', 'Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X)'),
            ('Desktop', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
            ('FindMyTaste App', 'FindMyTaste/1.0 (iPhone; iOS 14.0)'),
        ]
        
        factory = RequestFactory()
        
        for name, user_agent in test_cases:
            request = factory.get('/')
            request.META['HTTP_USER_AGENT'] = user_agent
            
            device_info = MobileDetection.get_device_info(request)
            
            self.stdout.write(f'  {name}:')
            self.stdout.write(f'    Mobile: {device_info["is_mobile"]}')
            self.stdout.write(f'    Tablet: {device_info["is_tablet"]}')
            self.stdout.write(f'    App: {device_info["is_app"]}')
            self.stdout.write(f'    Platform: {device_info["platform"]}')
            self.stdout.write('')
    
    def test_specific_route(self, route, params_str=None):
        """Test a specific deep link route."""
        self.stdout.write(f'🔗 Testing Route: {route}\n')
        
        # Parse parameters
        params = {}
        if params_str:
            try:
                params = json.loads(params_str)
            except json.JSONDecodeError:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Invalid JSON parameters: {params_str}')
                )
        
        # Test deep link generation
        manager = DeepLinkManager()
        
        try:
            # Generate iOS deep link
            ios_link = manager.generate_deep_link(route, platform='ios', **params)
            self.stdout.write(f'📱 iOS Deep Link: {ios_link}')
            
            # Generate Android deep link
            android_link = manager.generate_deep_link(route, platform='android', **params)
            self.stdout.write(f'🤖 Android Deep Link: {android_link}')
            
            # Generate Universal Link
            universal_link = manager.generate_deep_link(route, platform='universal', **params)
            self.stdout.write(f'🌐 Universal Link: {universal_link}')
            
            # Test QR code generation
            qr_generator = QRCodeGenerator()
            qr_code = qr_generator.generate_qr_code(universal_link, format='base64')
            
            if qr_code:
                self.stdout.write('📱 QR Code: Generated successfully')
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️  QR Code: Generation failed')
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error testing route: {e}')
            )
        
        self.stdout.write('')
    
    def generate_qr_codes(self):
        """Generate QR codes for all supported routes."""
        self.stdout.write('📱 Generating QR Codes...\n')
        
        supported_routes = getattr(settings, 'SUPPORTED_ROUTES', {})
        qr_generator = QRCodeGenerator()
        manager = DeepLinkManager()
        
        for route in supported_routes.keys():
            try:
                # Generate universal link
                universal_link = manager.generate_deep_link(route, platform='universal')
                
                # Generate QR code
                qr_code = qr_generator.generate_qr_code(universal_link)
                
                if qr_code:
                    self.stdout.write(f'  ✅ {route}: QR code generated')
                else:
                    self.stdout.write(f'  ❌ {route}: QR code failed')
                    
            except Exception as e:
                self.stdout.write(f'  ❌ {route}: Error - {e}')
        
        self.stdout.write('')
    
    def show_analytics(self):
        """Show analytics summary."""
        self.stdout.write('📊 Analytics Summary...\n')
        
        try:
            analytics = DeepLinkAnalytics.get_analytics_summary()
            
            self.stdout.write(f'  Total Clicks: {analytics.get("total_clicks", 0)}')
            self.stdout.write(f'  Total Installs: {analytics.get("total_installs", 0)}')
            self.stdout.write(f'  Conversion Rate: {analytics.get("conversion_rate", 0):.2f}%')
            
            popular_routes = analytics.get('popular_routes', {})
            if popular_routes:
                self.stdout.write('  Popular Routes:')
                for route, count in popular_routes.items():
                    self.stdout.write(f'    • {route}: {count} clicks')
            
            platform_breakdown = analytics.get('platform_breakdown', {})
            if platform_breakdown:
                self.stdout.write('  Platform Breakdown:')
                for platform, count in platform_breakdown.items():
                    self.stdout.write(f'    • {platform}: {count} clicks')
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Analytics not available: {e}')
            )
        
        self.stdout.write('')
    
    def run_comprehensive_test(self):
        """Run comprehensive deep linking tests."""
        self.stdout.write('🧪 Running Comprehensive Tests...\n')
        
        # Test configuration
        self.validate_configuration()
        
        # Test mobile detection
        self.test_mobile_detection()
        
        # Test common routes
        common_routes = ['marketplace', 'login', 'product_detail']
        
        for route in common_routes:
            if route == 'product_detail':
                self.test_specific_route(route, '{"product_id": "123"}')
            else:
                self.test_specific_route(route)
        
        # Test share link generation
        self.stdout.write('🔗 Testing Share Links...\n')
        
        try:
            share_link = ShareLinkGenerator.generate_share_link(
                'marketplace',
                title='Check out FindMyTaste!',
                description='Discover amazing food near you'
            )
            
            if share_link:
                self.stdout.write(f'  ✅ Share link generated: {share_link}')
            else:
                self.stdout.write('  ❌ Share link generation failed')
                
        except Exception as e:
            self.stdout.write(f'  ❌ Share link error: {e}')
        
        self.stdout.write('')
        
        # Show analytics
        self.show_analytics()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Comprehensive testing completed!')
        )