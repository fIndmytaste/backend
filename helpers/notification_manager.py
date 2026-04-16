import json
import os
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.template import Template, Context
import logging

logger = logging.getLogger(__name__)

class NotificationManager:
    """
    Manages notification templates and handles template processing
    """
    
    def __init__(self):
        self.templates = None
        self.load_templates()
    
    def load_templates(self):
        """Load notification templates from JSON file"""
        try:
            template_path = os.path.join(settings.BASE_DIR, 'notification_templates.json')
            with open(template_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                self.templates = data.get('notification_templates', {})
                logger.info("Notification templates loaded successfully")
        except FileNotFoundError:
            logger.error("Notification templates file not found")
            self.templates = {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing notification templates JSON: {e}")
            self.templates = {}
    
    def get_template(self, user_type: str, category: str, template_key: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific notification template
        
        Args:
            user_type: 'customer', 'vendor', or 'rider'
            category: Template category (e.g., 'account_onboarding', 'orders')
            template_key: Specific template key (e.g., 'signup', 'order_created')
        
        Returns:
            Template dictionary or None if not found
        """
        try:
            return self.templates[user_type][category][template_key]
        except KeyError:
            logger.warning(f"Template not found: {user_type}.{category}.{template_key}")
            return None
    
    def process_template(self, template: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, str]:
        """
        Process a template with given variables
        
        Args:
            template: Template dictionary
            variables: Variables to substitute in template
        
        Returns:
            Processed template with title and body
        """
        if not template:
            return {"title": "", "body": ""}
        
        try:
            # Process title
            title_template = Template(template.get('title', ''))
            processed_title = title_template.render(Context(variables))
            
            # Process body
            body_template = Template(template.get('body', ''))
            processed_body = body_template.render(Context(variables))
            
            return {
                "title": processed_title,
                "body": processed_body,
                "type": template.get('type', ''),
                "category": template.get('category', ''),
                "priority": template.get('priority', 'medium')
            }
        except Exception as e:
            logger.error(f"Error processing template: {e}")
            return {"title": "Notification", "body": "You have a new notification"}
    
    def create_notification(self, user_type: str, category: str, template_key: str, 
                          variables: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Create a notification from template
        
        Args:
            user_type: 'customer', 'vendor', or 'rider'
            category: Template category
            template_key: Specific template key
            variables: Variables for template processing
        
        Returns:
            Processed notification
        """
        if variables is None:
            variables = {}
        
        template = self.get_template(user_type, category, template_key)
        return self.process_template(template, variables)
    
    def get_templates_by_category(self, user_type: str, category: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all templates for a specific user type and category
        
        Args:
            user_type: 'customer', 'vendor', or 'rider'
            category: Template category
        
        Returns:
            Dictionary of templates in the category
        """
        try:
            return self.templates[user_type][category]
        except KeyError:
            logger.warning(f"Category not found: {user_type}.{category}")
            return {}
    
    def get_all_templates_for_user(self, user_type: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Get all templates for a specific user type
        
        Args:
            user_type: 'customer', 'vendor', or 'rider'
        
        Returns:
            All templates for the user type
        """
        try:
            return self.templates[user_type]
        except KeyError:
            logger.warning(f"User type not found: {user_type}")
            return {}
    
    def validate_template_variables(self, template: Dict[str, Any], variables: Dict[str, Any]) -> List[str]:
        """
        Validate that all required variables are provided
        
        Args:
            template: Template dictionary
            variables: Provided variables
        
        Returns:
            List of missing variables
        """
        required_vars = template.get('variables', [])
        missing_vars = []
        
        for var in required_vars:
            if var not in variables:
                missing_vars.append(var)
        
        return missing_vars
    
    def get_template_info(self, user_type: str, category: str, template_key: str) -> Dict[str, Any]:
        """
        Get template information including metadata
        
        Args:
            user_type: 'customer', 'vendor', or 'rider'
            category: Template category
            template_key: Specific template key
        
        Returns:
            Template information with metadata
        """
        template = self.get_template(user_type, category, template_key)
        if not template:
            return {}
        
        return {
            "template": template,
            "required_variables": template.get('variables', []),
            "category": template.get('category', ''),
            "priority": template.get('priority', 'medium'),
            "type": template.get('type', '')
        }


# Convenience functions for common notification types
def send_customer_order_notification(order_id: str, notification_type: str, **kwargs):
    """Send order-related notification to customer"""
    manager = NotificationManager()
    variables = {"order_id": order_id, **kwargs}
    return manager.create_notification("customer", "orders", notification_type, variables)

def send_vendor_order_notification(order_id: str, notification_type: str, **kwargs):
    """Send order-related notification to vendor"""
    manager = NotificationManager()
    variables = {"order_id": order_id, **kwargs}
    return manager.create_notification("vendor", "orders", notification_type, variables)

def send_rider_order_notification(order_id: str, notification_type: str, **kwargs):
    """Send order-related notification to rider"""
    manager = NotificationManager()
    variables = {"order_id": order_id, **kwargs}
    return manager.create_notification("rider", "orders", notification_type, variables)

def send_account_notification(user_type: str, notification_type: str, **kwargs):
    """Send account-related notification"""
    manager = NotificationManager()
    return manager.create_notification(user_type, "account_onboarding", notification_type, kwargs)

def send_security_notification(user_type: str, notification_type: str, **kwargs):
    """Send security-related notification"""
    manager = NotificationManager()
    category = "account_onboarding" if notification_type in ["password_change", "security_alert"] else "system_security"
    return manager.create_notification(user_type, category, notification_type, kwargs)

# Example usage functions
def example_notifications():
    """Example usage of the notification system"""
    manager = NotificationManager()
    
    # Customer order notification
    customer_order = manager.create_notification(
        "customer", 
        "orders", 
        "order_delivered", 
        {"order_id": "ORD123456"}
    )
    print("Customer Order Notification:", customer_order)
    
    # Vendor new order notification
    vendor_order = manager.create_notification(
        "vendor", 
        "orders", 
        "new_order", 
        {"order_id": "ORD123456"}
    )
    print("Vendor Order Notification:", vendor_order)
    
    # Rider assignment notification
    rider_assignment = manager.create_notification(
        "rider", 
        "orders", 
        "order_accepted", 
        {"order_id": "ORD123456"}
    )
    print("Rider Assignment Notification:", rider_assignment)
    
    # Welcome notification
    welcome = manager.create_notification(
        "customer", 
        "account_onboarding", 
        "signup", 
        {"app_name": "FindMyTaste"}
    )
    print("Welcome Notification:", welcome)

if __name__ == "__main__":
    example_notifications()