"""
Notification System Usage Examples
Demonstrates how to use the notification system in various scenarios
"""

from django.contrib.auth.models import User
from helpers.notification_integration import (
    send_login_notification, 
    send_security_alert, 
    send_account_notification
)
from helpers.notification_manager import NotificationManager

# Example 1: Basic Login Notification
def example_login_notification():
    """
    Example of sending a login notification
    """
    # Assuming you have a user object
    user = User.objects.get(id=1)  # Replace with actual user
    
    # Send login notification (automatically determines user type and sends push notification)
    result = send_login_notification(user)
    
    if result['success']:
        print(f"Login notification sent successfully: {result['notification']}")
    else:
        print(f"Failed to send login notification: {result['error']}")

# Example 2: Security Alert
def example_security_alert():
    """
    Example of sending a security alert for suspicious login
    """
    user = User.objects.get(id=1)  # Replace with actual user
    
    # Send security alert
    result = send_security_alert(
        user=user,
        device_info="iPhone 12 Pro",
        location="Lagos, Nigeria",
        ip_address="192.168.1.1"
    )
    
    if result['success']:
        print(f"Security alert sent: {result['notification']}")

# Example 3: Profile Update Notification
def example_profile_update():
    """
    Example of sending a profile update notification
    """
    user = User.objects.get(id=1)  # Replace with actual user
    
    # Send profile update notification
    result = send_account_notification(
        user=user,
        notification_type='profile_updated'
    )
    
    if result['success']:
        print(f"Profile update notification sent: {result['notification']}")

# Example 4: Password Change Notification
def example_password_change():
    """
    Example of sending a password change notification
    """
    user = User.objects.get(id=1)  # Replace with actual user
    
    # Send password change notification
    result = send_account_notification(
        user=user,
        notification_type='password_change'
    )
    
    if result['success']:
        print(f"Password change notification sent: {result['notification']}")

# Example 5: Using NotificationManager Directly
def example_direct_notification_manager():
    """
    Example of using NotificationManager directly for more control
    """
    manager = NotificationManager()
    
    # Get a specific template
    template = manager.get_template('customer', 'account_onboarding', 'login')
    print(f"Template: {template}")
    
    # Create a notification with custom variables
    notification = manager.create_notification(
        user_type='vendor',
        category='account_onboarding',
        template_key='login',
        variables={'name': 'John Doe'}
    )
    print(f"Generated notification: {notification}")
    
    # Get all templates for a user type
    all_templates = manager.get_all_templates_for_user('customer')
    print(f"All customer templates: {list(all_templates.keys())}")

# Example 6: Integration in Django Views
def example_view_integration():
    """
    Example of how to integrate notifications in Django views
    """
    # This is how you would use it in your LoginAPIView
    
    # In your view's post method:
    def post(self, request, *args, **kwargs):
        # ... your existing login logic ...
        
        if user is not None and user.is_active:
            # Send login notification
            try:
                send_login_notification(user)
            except Exception as e:
                # Log the error but don't fail the login process
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send login notification: {e}")
            
            # ... rest of your login logic ...

# Example 7: Bulk Notifications
def example_bulk_notifications():
    """
    Example of sending notifications to multiple users
    """
    from helpers.notification_integration import NotificationIntegration
    
    integration = NotificationIntegration()
    
    # Get all active users
    users = User.objects.filter(is_active=True)
    
    # Send a notification to all users
    for user in users:
        try:
            result = integration.send_account_notification_generic(
                user=user,
                notification_type='login',
                name=user.full_name or user.email.split('@')[0]
            )
            print(f"Notification sent to {user.email}: {result['success']}")
        except Exception as e:
            print(f"Failed to send notification to {user.email}: {e}")

# Example 8: Custom Notification Data
def example_custom_notification_data():
    """
    Example of sending notifications with custom data
    """
    from helpers.push_notification import NotificationHelper
    from helpers.notification_manager import NotificationManager
    
    user = User.objects.get(id=1)  # Replace with actual user
    manager = NotificationManager()
    push_helper = NotificationHelper()
    
    # Create custom notification
    notification = manager.create_notification(
        user_type='customer',
        category='account_onboarding',
        template_key='login',
        variables={'name': user.full_name}
    )
    
    # Send with custom data
    push_helper.send_to_user_async(
        user=user,
        title=notification['title'],
        body=notification['body'],
        data={
            'type': 'login',
            'custom_field': 'custom_value',
            'timestamp': str(notification['timestamp']),
            'deep_link': 'findmytaste://dashboard'
        }
    )

# Example 9: Error Handling
def example_error_handling():
    """
    Example of proper error handling with notifications
    """
    user = User.objects.get(id=1)  # Replace with actual user
    
    try:
        result = send_login_notification(user)
        
        if result['success']:
            print("Notification sent successfully")
            # Log success
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Login notification sent to user {user.id}")
        else:
            print(f"Notification failed: {result['error']}")
            # Handle failure (maybe retry, log, etc.)
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        # Handle unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error sending notification: {e}")

# Example 10: Testing Notifications
def example_testing():
    """
    Example of testing notifications
    """
    from helpers.notification_manager import NotificationManager
    
    manager = NotificationManager()
    
    # Test template loading
    assert manager.templates is not None, "Templates should be loaded"
    
    # Test template retrieval
    login_template = manager.get_template('customer', 'account_onboarding', 'login')
    assert login_template is not None, "Login template should exist"
    
    # Test notification creation
    notification = manager.create_notification(
        user_type='customer',
        category='account_onboarding',
        template_key='login',
        variables={'name': 'Test User'}
    )
    assert 'title' in notification, "Notification should have title"
    assert 'body' in notification, "Notification should have body"
    assert 'Test User' in notification['title'], "Name should be in title"
    
    print("All tests passed!")

if __name__ == "__main__":
    # Run examples (uncomment the ones you want to test)
    # example_login_notification()
    # example_security_alert()
    # example_profile_update()
    # example_password_change()
    # example_direct_notification_manager()
    # example_bulk_notifications()
    # example_custom_notification_data()
    # example_error_handling()
    example_testing()