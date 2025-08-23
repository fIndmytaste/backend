# helpers/notification_helper.py
import threading
import logging
from typing import List, Dict, Any, Optional, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.contrib.auth.models import User
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from helpers.services.firebase_service import FirebaseNotificationService

logger = logging.getLogger(__name__)

class NotificationHelper:
    """
    Helper class for sending Firebase notifications with threading support
    """
    
    def __init__(self, max_workers: int = 5):
        """
        Initialize the notification helper
        
        Args:
            max_workers: Maximum number of worker threads for bulk operations
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    
    def send_to_token_async(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> threading.Thread:
        """
        Send notification to a raw FCM device token asynchronously
        """
        def _send_notification():
            try:
                result = FirebaseNotificationService.send_to_token(
                    token=token,
                    title=title,
                    body=body,
                    data=data,
                    image_url=image_url
                )
                logger.info(f"Notification sent to token: {result}")

                if callback:
                    callback(result, token)

                return result
            except Exception as e:
                error_msg = f"Error sending notification to token {token}: {str(e)}"
                logger.error(error_msg)
                return {"success": False, "error": str(e)}

        thread = threading.Thread(target=_send_notification)
        thread.daemon = True
        thread.start()
        return thread


    
    def send_to_user_async(
        self,
        user: Union[User, int, str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> threading.Thread:
        """
        Send notification to a user asynchronously
        
        Args:
            user: User object, user ID, or username
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Optional image URL
            callback: Optional callback function to execute after sending
        
        Returns:
            threading.Thread: The thread handling the notification
        """
        def _send_notification():
            try:
                # Resolve user if needed
                user_obj = self._resolve_user(user)
                if not user_obj:
                    logger.error(f"User not found: {user}")
                    return {"success": False, "error": "User not found"}
                
                # Send notification
                result = FirebaseNotificationService.send_notification_to_user(
                    user=user_obj,
                    title=title,
                    body=body,
                    data=data,
                    image_url=image_url
                )
                
                logger.info(f"Notification sent to user {user_obj.username}: {result}")
                
                # Execute callback if provided
                if callback:
                    callback(result, user_obj)
                
                return result
                
            except Exception as e:
                error_msg = f"Error sending notification to user {user}: {str(e)}"
                logger.error(error_msg)
                return {"success": False, "error": str(e)}
        
        thread = threading.Thread(target=_send_notification)
        thread.daemon = True
        thread.start()
        return thread
    

    def send_to_topic_async(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> threading.Thread:
        """
        Send notification to a topic asynchronously
        
        Args:
            topic: Firebase topic name
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Optional image URL
            callback: Optional callback function to execute after sending
        
        Returns:
            threading.Thread: The thread handling the notification
        """
        def _send_notification():
            try:
                result = FirebaseNotificationService.send_to_topic(
                    topic=topic,
                    title=title,
                    body=body,
                    data=data,
                    image_url=image_url
                )
                
                logger.info(f"Notification sent to topic {topic}: {result}")
                
                # Execute callback if provided
                if callback:
                    callback(result, topic)
                
                return result
                
            except Exception as e:
                error_msg = f"Error sending notification to topic {topic}: {str(e)}"
                logger.error(error_msg)
                return {"success": False, "error": str(e)}
        
        thread = threading.Thread(target=_send_notification)
        thread.daemon = True
        thread.start()
        return thread
    
    def send_to_multiple_users_async(
        self,
        users: List[Union[User, int, str]],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> List[threading.Thread]:
        """
        Send notifications to multiple users asynchronously
        
        Args:
            users: List of User objects, user IDs, or usernames
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Optional image URL
            callback: Optional callback function to execute after each send
        
        Returns:
            List[threading.Thread]: List of threads handling the notifications
        """
        threads = []
        
        for user in users:
            thread = self.send_to_user_async(
                user=user,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                callback=callback
            )
            threads.append(thread)
        
        return threads
    
    def send_bulk_notifications_async(
        self,
        notifications: List[Dict[str, Any]],
        callback: Optional[Callable] = None
    ) -> List[threading.Thread]:
        """
        Send multiple different notifications asynchronously
        
        Args:
            notifications: List of notification dictionaries with keys:
                - type: 'user' or 'topic'
                - target: User object/ID/username or topic name
                - title: Notification title
                - body: Notification body
                - data: Optional data payload
                - image_url: Optional image URL
            callback: Optional callback function to execute after each send
        
        Returns:
            List[threading.Thread]: List of threads handling the notifications
        """
        threads = []
        
        for notification in notifications:
            if notification.get('type') == 'user':
                thread = self.send_to_user_async(
                    user=notification['target'],
                    title=notification['title'],
                    body=notification['body'],
                    data=notification.get('data'),
                    image_url=notification.get('image_url'),
                    callback=callback
                )
            elif notification.get('type') == 'topic':
                thread = self.send_to_topic_async(
                    topic=notification['target'],
                    title=notification['title'],
                    body=notification['body'],
                    data=notification.get('data'),
                    image_url=notification.get('image_url'),
                    callback=callback
                )
            else:
                logger.error(f"Invalid notification type: {notification.get('type')}")
                continue
            
            threads.append(thread)
        
        return threads
    
    def send_to_users_with_executor(
        self,
        users: List[Union[User, int, str]],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Send notifications to multiple users using ThreadPoolExecutor
        This method waits for all notifications to complete and returns results
        
        Args:
            users: List of User objects, user IDs, or usernames
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Optional image URL
            timeout: Timeout in seconds for all operations
        
        Returns:
            Dict with success/failure counts and results
        """
        def send_to_single_user(user):
            try:
                user_obj = self._resolve_user(user)
                if not user_obj:
                    return {"user": str(user), "success": False, "error": "User not found"}
                
                result = FirebaseNotificationService.send_notification_to_user(
                    user=user_obj,
                    title=title,
                    body=body,
                    data=data,
                    image_url=image_url
                )
                
                return {
                    "user": user_obj.username,
                    "user_id": user_obj.id,
                    **result
                }
            except Exception as e:
                return {"user": str(user), "success": False, "error": str(e)}
        
      
        future_to_user = {
            self._executor.submit(send_to_single_user, user): user 
            for user in users
        }
        
        results = []
        success_count = 0
        failure_count = 0
        
        # Collect results
        for future in as_completed(future_to_user, timeout=timeout):
            try:
                result = future.result()
                results.append(result)
                
                if result.get('success'):
                    success_count += 1
                else:
                    failure_count += 1
                    
            except Exception as e:
                user = future_to_user[future]
                results.append({
                    "user": str(user),
                    "success": False,
                    "error": f"Task execution error: {str(e)}"
                })
                failure_count += 1
        
        return {
            "total": len(users),
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results
        }
    
    def _resolve_user(self, user: Union[User, int, str]) -> Optional[User]:
        """
        Resolve user from different input types
        
        Args:
            user: User object, user ID, or username
        
        Returns:
            User object or None if not found
        """
        if isinstance(user, User):
            return user
        
        try:
            if isinstance(user, int):
                return User.objects.get(id=user)
            elif isinstance(user, str):
                if user.isdigit():
                    return User.objects.get(id=int(user))
                else:
                    return User.objects.get(username=user)
        except ObjectDoesNotExist:
            return None
        
        return None
    
    def wait_for_threads(self, threads: List[threading.Thread], timeout: Optional[int] = None):
        """
        Wait for all threads to complete
        
        Args:
            threads: List of threads to wait for
            timeout: Maximum time to wait for each thread
        """
        for thread in threads:
            thread.join(timeout=timeout)
    
    def shutdown(self):
        """
        Shutdown the thread pool executor
        """
        self._executor.shutdown(wait=True)

# Usage examples and convenience functions
class NotificationTemplates:
    """
    Pre-defined notification templates for common use cases
    """
    
    @staticmethod
    def welcome_notification(user: Union[User, int, str]) -> Dict[str, Any]:
        user_obj = NotificationHelper()._resolve_user(user)
        return {
            "type": "user",
            "target": user,
            "title": "Welcome!",
            "body": f"Welcome to our app, {user_obj.first_name or user_obj.username}!",
            "data": {
                "screen": "welcome",
                "user_id": str(user_obj.id) if user_obj else ""
            }
        }
    
    @staticmethod
    def order_confirmation(user: Union[User, int, str], order_id: str) -> Dict[str, Any]:
        return {
            "type": "user",
            "target": user,
            "title": "Order Confirmed",
            "body": f"Your order #{order_id} has been confirmed!",
            "data": {
                "screen": "order_details",
                "order_id": order_id,
                "type": "order_confirmation"
            }
        }
    
    @staticmethod
    def promotional_notification(topic: str, title: str, body: str, promo_code: str = None) -> Dict[str, Any]:
        data = {"type": "promotion"}
        if promo_code:
            data["promo_code"] = promo_code
            
        return {
            "type": "topic",
            "target": topic,
            "title": title,
            "body": body,
            "data": data
        }

# Singleton instance for global use
notification_helper = NotificationHelper()

# Convenience functions for quick access
def send_welcome_notification(user: Union[User, int, str], callback: Optional[Callable] = None) -> threading.Thread:
    """Send welcome notification to user"""
    user_obj = notification_helper._resolve_user(user)
    return notification_helper.send_to_user_async(
        user=user,
        title="Welcome!",
        body=f"Welcome to our app, {user_obj.first_name or user_obj.username if user_obj else 'there'}!",
        data={"screen": "welcome", "user_id": str(user_obj.id) if user_obj else ""},
        callback=callback
    )

def send_order_notification(user: Union[User, int, str], order_id: str, callback: Optional[Callable] = None) -> threading.Thread:
    """Send order confirmation notification"""
    return notification_helper.send_to_user_async(
        user=user,
        title="Order Confirmed",
        body=f"Your order #{order_id} has been confirmed!",
        data={"screen": "order_details", "order_id": order_id, "type": "order_confirmation"},
        callback=callback
    )

def send_promotional_notification(topic: str, title: str, body: str, promo_code: str = None, callback: Optional[Callable] = None) -> threading.Thread:
    """Send promotional notification to topic"""
    data = {"type": "promotion"}
    if promo_code:
        data["promo_code"] = promo_code
        
    return notification_helper.send_to_topic_async(
        topic=topic,
        title=title,
        body=body,
        data=data,
        callback=callback
    )





