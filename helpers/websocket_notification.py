from typing import Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

from product.models import Order
from helpers.push_notification import notification_helper


def send_order_status_update_notification(order: Order, status: str, message: Optional[str] = None):
    """
    Send a push notification to the customer about an order status update.
    
    Args:
        order (Order): The order instance.
        status (str): The updated status (e.g., 'confirmed', 'shipped', 'delivered').
        message (Optional[str]): Custom message to show in the notification body.
    """
    if not message:
        # Default messages by status
        default_messages = {
            "confirmed": "Your order has been accepted by the vendor.",
            "shipped": "Your order is on the way!",
            "delivered": "Your order has been delivered. Enjoy!",
            "cancelled": "Your order has been cancelled.",
        }
        message = default_messages.get(status, "Order status updated.")
    
    try:
        notification_helper.send_to_user_async(
            user=order.user,
            title=f"Order {status.capitalize()}!",
            body=message,
            data={"event": "order_status_update", "order_id": order.id, "status": status}
        )
    except Exception as e:
        print(f"Push notification error: {e}")



def send_order_accepted_notification_customer(order:Order):
    """
    Send order accepted notification to customer
    Call this function when a vendor accepts an order
    """
    try:
        customer_group_name = f'customer_{order.user.id}'
        try:
            channel_layer = get_channel_layer()
            

            async_to_sync(channel_layer.group_send)(
                customer_group_name,
                {
                    'type': 'order_accepted_notification',
                    'data': {
                        'order_id': str(order.id),
                        'vendor': {
                            'name': order.vendor.name,  
                        },
                        'estimated_delivery_time': order.new_estimated_delivery_time,  
                        'accepted_at': timezone.now().isoformat(),
                        'status': 'confirmed',
                        'message': 'Your order has been accepted by the vendor!'
                    }
                }
            )
        except:pass

        try:
            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                customer_group_name,
                {
                    'type': 'order_status_update',
                    'data': {
                        'order_id': str(order.id), 
                        'status': 'confirmed',
                        'message': 'Order status updated!'
                    }
                }
            )
        except:pass

        # Also send push notification
        try:
            thread = notification_helper.send_to_user_async(
                user=order.user,
                title="Order Accepted! 🎉",
                body=f"Your order has been accepted by the vendor. Preparing your order now!",
                data={"event": "order_accepted", "order_id": order.id}
            )
        except Exception as e:
            print(f"Push notification error: {e}")

        
        try:
            send_order_status_update_notification(order, 'confirmed')
        except Exception as e:
            print(f"Push notification error: {e}")

    except Exception as e:
        print(f"WebSocket notification error: {e}")