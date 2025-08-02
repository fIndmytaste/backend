import logging
from typing import List, Dict, Any, Optional
from account.models import FCMToken, PushNotificationLog
from firebase_admin import messaging
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

class FirebaseNotificationService:

    @staticmethod
    def send_notification_to_token(token: str, title: str, body: str, data=None, image_url=None):
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
                image=image_url
            ),
            data=data or {},
            token=token
        )
        response = messaging.send(message)
        return {"response": response}
    
    @staticmethod
    def send_notification_to_user(
        user: User,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification to all active tokens of a user"""
        
        tokens = FCMToken.objects.filter(user=user, is_active=True)
        if not tokens.exists():
            return {"success": False, "error": "No active FCM tokens found for user"}
        
        token_strings = [token.token for token in tokens]
        
        return FirebaseNotificationService.send_multicast_notification(
            tokens=token_strings,
            title=title,
            body=body,
            data=data,
            image_url=image_url,
            user=user
        )
    
    @staticmethod
    def send_multicast_notification(
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Send notification to multiple tokens"""
        
        if not tokens:
            return {"success": False, "error": "No tokens provided"}
        
        # Prepare notification
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url
        )
        
        # Prepare data payload (must be strings)
        data_payload = {}
        if data:
            data_payload = {str(k): str(v) for k, v in data.items()}
        
        # Create multicast message
        message = messaging.MulticastMessage(
            notification=notification,
            data=data_payload,
            tokens=tokens,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='ic_notification',
                    color='#FF6B35',
                    sound='default'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1
                    )
                )
            )
        )
        
        try:
            # Send the message
            response = messaging.send_multicast(message)
            
            # Log the notification
            if user:
                PushNotificationLog.objects.create(
                    user=user,
                    title=title,
                    body=body,
                    data=data or {},
                    status='sent' if response.success_count > 0 else 'failed',
                    firebase_message_id=str(response.responses[0].message_id) if response.responses else None
                )
            
            # Handle invalid tokens
            if response.failure_count > 0:
                invalid_tokens = []
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        invalid_tokens.append(tokens[idx])
                        logger.error(f"Failed to send to token {tokens[idx]}: {resp.exception}")
                
      
                FCMToken.objects.filter(token__in=invalid_tokens).update(is_active=False)
            
            return {
                "success": response.success_count > 0,
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            
            # Log failed notification
            if user:
                PushNotificationLog.objects.create(
                    user=user,
                    title=title,
                    body=body,
                    data=data or {},
                    status='failed',
                    error_message=str(e)
                )
            
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def send_to_topic(
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification to a topic"""
        
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url
        )
        
        data_payload = {}
        if data:
            data_payload = {str(k): str(v) for k, v in data.items()}
        
        message = messaging.Message(
            notification=notification,
            data=data_payload,
            topic=topic,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='ic_notification',
                    color='#FF6B35',
                    sound='default'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1
                    )
                )
            )
        )
        
        try:
            message_id = messaging.send(message)
            return {"success": True, "message_id": message_id}
        except Exception as e:
            logger.error(f"Error sending topic notification: {str(e)}")
            return {"success": False, "error": str(e)}


