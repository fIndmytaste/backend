from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from .notification_manager import NotificationManager
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_notification(request):
    """
    Send a notification using the template system
    
    Expected payload:
    {
        "user_type": "customer|vendor|rider",
        "category": "category_name",
        "template_key": "template_name",
        "variables": {"key": "value"},
        "recipient_id": "user_id"
    }
    """
    try:
        data = request.data
        user_type = data.get('user_type')
        category = data.get('category')
        template_key = data.get('template_key')
        variables = data.get('variables', {})
        recipient_id = data.get('recipient_id')
        
        # Validate required fields
        if not all([user_type, category, template_key]):
            return Response({
                'error': 'user_type, category, and template_key are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create notification
        manager = NotificationManager()
        notification = manager.create_notification(user_type, category, template_key, variables)
        
        if not notification.get('title'):
            return Response({
                'error': 'Template not found or processing failed'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Here you would typically send the notification via your preferred method
        # (push notification, email, SMS, etc.)
        # For now, we'll just return the processed notification
        
        response_data = {
            'success': True,
            'notification': notification,
            'recipient_id': recipient_id,
            'template_info': {
                'user_type': user_type,
                'category': category,
                'template_key': template_key
            }
        }
        
        logger.info(f"Notification sent to {user_type} {recipient_id}: {template_key}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_notification_templates(request):
    """
    Get available notification templates
    
    Query parameters:
    - user_type: Filter by user type (customer, vendor, rider)
    - category: Filter by category
    """
    try:
        user_type = request.GET.get('user_type')
        category = request.GET.get('category')
        
        manager = NotificationManager()
        
        if user_type and category:
            templates = manager.get_templates_by_category(user_type, category)
        elif user_type:
            templates = manager.get_all_templates_for_user(user_type)
        else:
            templates = manager.templates
        
        return Response({
            'templates': templates,
            'filters': {
                'user_type': user_type,
                'category': category
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching templates: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_template_info(request, user_type, category, template_key):
    """
    Get detailed information about a specific template
    """
    try:
        manager = NotificationManager()
        template_info = manager.get_template_info(user_type, category, template_key)
        
        if not template_info:
            return Response({
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response(template_info, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching template info: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def preview_notification(request):
    """
    Preview a notification without sending it
    
    Expected payload:
    {
        "user_type": "customer|vendor|rider",
        "category": "category_name",
        "template_key": "template_name",
        "variables": {"key": "value"}
    }
    """
    try:
        data = request.data
        user_type = data.get('user_type')
        category = data.get('category')
        template_key = data.get('template_key')
        variables = data.get('variables', {})
        
        # Validate required fields
        if not all([user_type, category, template_key]):
            return Response({
                'error': 'user_type, category, and template_key are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        manager = NotificationManager()
        
        # Get template info
        template_info = manager.get_template_info(user_type, category, template_key)
        if not template_info:
            return Response({
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate variables
        missing_vars = manager.validate_template_variables(template_info['template'], variables)
        
        # Process notification
        notification = manager.create_notification(user_type, category, template_key, variables)
        
        return Response({
            'preview': notification,
            'template_info': template_info,
            'missing_variables': missing_vars,
            'provided_variables': variables
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error previewing notification: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Convenience functions for common notification scenarios
def notify_order_status_change(order, status_type, **extra_vars):
    """
    Send order status notifications to all relevant parties
    
    Args:
        order: Order object
        status_type: Type of status change
        **extra_vars: Additional variables for templates
    """
    manager = NotificationManager()
    
    # Notification mappings for different order statuses
    status_mappings = {
        'created': {
            'customer': ('orders', 'order_created'),
            'vendor': ('orders', 'new_order')
        },
        'accepted': {
            'customer': ('orders', 'vendor_accepted'),
            'vendor': ('orders', 'order_accepted')
        },
        'rider_assigned': {
            'customer': ('orders', 'rider_assigned'),
            'rider': ('orders', 'new_order_available')
        },
        'picked_up': {
            'customer': ('orders', 'order_picked_up'),
            'vendor': ('orders', 'order_picked_up'),
            'rider': ('orders', 'order_picked_up')
        },
        'delivered': {
            'customer': ('orders', 'order_delivered'),
            'vendor': ('orders', 'order_delivered'),
            'rider': ('orders', 'order_delivered')
        },
        'cancelled': {
            'customer': ('orders', 'order_cancelled'),
            'vendor': ('orders', 'order_cancelled_by_customer'),
            'rider': ('orders', 'order_cancelled')
        }
    }
    
    notifications = []
    mapping = status_mappings.get(status_type, {})
    
    for user_type, (category, template_key) in mapping.items():
        variables = {
            'order_id': str(order.id),
            **extra_vars
        }
        
        notification = manager.create_notification(user_type, category, template_key, variables)
        notifications.append({
            'user_type': user_type,
            'notification': notification
        })
    
    return notifications

def notify_account_event(user, user_type, event_type, **extra_vars):
    """
    Send account-related notifications
    
    Args:
        user: User object
        user_type: 'customer', 'vendor', or 'rider'
        event_type: Type of account event
        **extra_vars: Additional variables
    """
    manager = NotificationManager()
    
    # Determine category based on event type
    if event_type in ['signup', 'login', 'profile_updated', 'password_change', 'security_alert']:
        category = 'account_onboarding' if user_type == 'customer' else 'account_review'
    else:
        category = 'account_onboarding'
    
    variables = {
        'name': getattr(user, 'first_name', ''),
        f'{user_type}_name': getattr(user, 'first_name', ''),
        'app_name': 'FindMyTaste',
        **extra_vars
    }
    
    return manager.create_notification(user_type, category, event_type, variables)