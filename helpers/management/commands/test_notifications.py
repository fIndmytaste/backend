from django.core.management.base import BaseCommand
from helpers.notification_manager import NotificationManager
import json

class Command(BaseCommand):
    help = 'Test notification templates and demonstrate usage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-type',
            type=str,
            choices=['customer', 'vendor', 'rider'],
            help='Test notifications for specific user type'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Test notifications for specific category'
        )
        parser.add_argument(
            '--template',
            type=str,
            help='Test specific template'
        )
        parser.add_argument(
            '--list-all',
            action='store_true',
            help='List all available templates'
        )

    def handle(self, *args, **options):
        manager = NotificationManager()
        
        if options['list_all']:
            self.list_all_templates(manager)
            return
        
        if options['user_type'] and options['category'] and options['template']:
            self.test_specific_template(manager, options['user_type'], 
                                      options['category'], options['template'])
        elif options['user_type']:
            self.test_user_type(manager, options['user_type'])
        else:
            self.run_comprehensive_test(manager)

    def list_all_templates(self, manager):
        """List all available templates"""
        self.stdout.write(self.style.SUCCESS('Available Notification Templates:'))
        self.stdout.write('=' * 50)
        
        for user_type in ['customer', 'vendor', 'rider']:
            self.stdout.write(f"\n{user_type.upper()} TEMPLATES:")
            templates = manager.get_all_templates_for_user(user_type)
            
            for category, category_templates in templates.items():
                self.stdout.write(f"  📁 {category}:")
                for template_key in category_templates.keys():
                    self.stdout.write(f"    - {template_key}")

    def test_specific_template(self, manager, user_type, category, template_key):
        """Test a specific template"""
        self.stdout.write(f"Testing template: {user_type}.{category}.{template_key}")
        
        template_info = manager.get_template_info(user_type, category, template_key)
        if not template_info:
            self.stdout.write(self.style.ERROR('Template not found!'))
            return
        
        # Create sample variables
        sample_vars = self.get_sample_variables(template_info['required_variables'])
        
        # Process template
        notification = manager.create_notification(user_type, category, template_key, sample_vars)
        
        self.stdout.write(self.style.SUCCESS('Template processed successfully:'))
        self.stdout.write(f"Title: {notification['title']}")
        self.stdout.write(f"Body: {notification['body']}")
        self.stdout.write(f"Type: {notification['type']}")
        self.stdout.write(f"Priority: {notification['priority']}")

    def test_user_type(self, manager, user_type):
        """Test all templates for a specific user type"""
        self.stdout.write(f"Testing all {user_type} templates:")
        self.stdout.write('=' * 40)
        
        templates = manager.get_all_templates_for_user(user_type)
        
        for category, category_templates in templates.items():
            self.stdout.write(f"\n📁 {category.upper()}:")
            
            for template_key, template in category_templates.items():
                sample_vars = self.get_sample_variables(template.get('variables', []))
                notification = manager.create_notification(user_type, category, template_key, sample_vars)
                
                self.stdout.write(f"  ✉️  {template_key}:")
                self.stdout.write(f"     Title: {notification['title']}")
                self.stdout.write(f"     Body: {notification['body'][:100]}...")

    def run_comprehensive_test(self, manager):
        """Run comprehensive test of the notification system"""
        self.stdout.write(self.style.SUCCESS('Running Comprehensive Notification Test'))
        self.stdout.write('=' * 60)
        
        # Test scenarios
        test_scenarios = [
            {
                'name': 'Customer Order Flow',
                'tests': [
                    ('customer', 'orders', 'order_created', {'order_id': 'ORD123456'}),
                    ('vendor', 'orders', 'new_order', {'order_id': 'ORD123456'}),
                    ('vendor', 'orders', 'order_accepted', {'order_id': 'ORD123456'}),
                    ('rider', 'orders', 'new_order_available', {'order_id': 'ORD123456'}),
                    ('rider', 'orders', 'order_accepted', {'order_id': 'ORD123456'}),
                    ('customer', 'orders', 'rider_assigned', {'order_id': 'ORD123456', 'rider_name': 'John Doe'}),
                    ('customer', 'orders', 'order_picked_up', {'order_id': 'ORD123456', 'rider_name': 'John Doe'}),
                    ('customer', 'orders', 'order_delivered', {'order_id': 'ORD123456'}),
                ]
            },
            {
                'name': 'Account Registration Flow',
                'tests': [
                    ('customer', 'account_onboarding', 'signup', {'app_name': 'FindMyTaste'}),
                    ('vendor', 'account_review', 'signup', {'app_name': 'FindMyTaste'}),
                    ('rider', 'account_review', 'signup', {'app_name': 'FindMyTaste'}),
                    ('vendor', 'account_review', 'account_approved', {}),
                    ('rider', 'account_review', 'account_approved', {}),
                ]
            },
            {
                'name': 'Security Notifications',
                'tests': [
                    ('customer', 'account_onboarding', 'password_change', {}),
                    ('vendor', 'account_review', 'security_alert', {}),
                    ('rider', 'account_review', 'security_alert', {}),
                ]
            }
        ]
        
        for scenario in test_scenarios:
            self.stdout.write(f"\n🎯 {scenario['name']}:")
            self.stdout.write('-' * 30)
            
            for user_type, category, template_key, variables in scenario['tests']:
                notification = manager.create_notification(user_type, category, template_key, variables)
                self.stdout.write(f"  📱 {user_type}: {notification['title']}")

    def get_sample_variables(self, required_vars):
        """Generate sample variables for testing"""
        sample_data = {
            'order_id': 'ORD123456',
            'rider_name': 'John Doe',
            'vendor_name': 'Pizza Palace',
            'name': 'Jane Smith',
            'app_name': 'FindMyTaste',
            'promo_details': '20% off your next order',
            'reward_details': '₦500 cashback',
            'ticket_id': 'TKT789',
            'start_time': '2:00 AM',
            'end_time': '4:00 AM',
            'amount': '2500',
            'delivery_count': '15',
            'rejection_reason': 'Incomplete documentation',
            'feature_details': 'Real-time order tracking',
            'incentive_details': 'Double earnings this weekend',
            'estimated_time': '30 minutes'
        }
        
        return {var: sample_data.get(var, f'sample_{var}') for var in required_vars}