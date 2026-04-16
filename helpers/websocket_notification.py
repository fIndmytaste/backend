from typing import Optional
from channels.layers import get_channel_layer
from account.models import Rider
from asgiref.sync import async_to_sync
from django.utils import timezone
import uuid
from datetime import datetime

from helpers.order_utils import get_distance_between_two_location
from product.models import Order
from helpers.push_notification import notification_helper
from rider.serializers import OrderSerializer


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


        riders = Rider.objects.filter(status='active')  # Mark all riders as unavailable to trigger new order notifications


        
        # I want to send and order event to riders
        # Notify riders about a new available order
        for rider in riders:
            distance = get_distance_between_two_location(
                lat1=float(rider.current_latitude),
                lon1=float(rider.current_longitude),
                lat2=float(order.vendor.location_latitude),
                lon2=float(order.vendor.location_longitude)
            )

            # Filter orders within 5-10km range
            if distance is not None and distance <= 10:
                continue  # Skip riders that are too far away (more than 10km)

            rider_group_name = f'riders_group_{rider.user.id}'
            try:
                # rider_group_name = 'riders_group'
                channel_layer = get_channel_layer()


                order_details = OrderSerializer(order).data
                formatted_order_details = format_object_fields(order_details)

                async_to_sync(channel_layer.group_send)(
                    rider_group_name,
                    {
                        'type': 'new_order_event',
                        'data': {
                            'order_id': str(order.id),
                            'order_details': formatted_order_details,
                            'vendor': {
                                'name': order.vendor.name,
                                'location': {
                                    'latitude': order.vendor.location_latitude,
                                    'longitude': order.vendor.location_longitude
                                }
                            },
                            'customer': {
                                'name': order.user.full_name,
                                'location': {
                                    'latitude': order.delivery_latitude,
                                    'longitude': order.delivery_longitude
                                }
                            },
                            'created_at': timezone.now().isoformat(),
                            'status': 'new',
                            'message': 'A new order is available for pickup!'
                        }
                    }
                )
            except Exception as e:
                print(f"WebSocket notification to riders error: {e}")


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


        
        try:
            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                customer_group_name,
                {
                    'type': 'order_status_update',
                    'data': {
                        'order_id': str(order.id), 
                        'status': 'looking_for_rider',
                        'message': 'Order status updated!'
                    }
                }
            )
        except:pass


        # update order status to looking_for_rider
        order.status = 'looking_for_rider'
        order.save()

    except Exception as e:
        print(f"WebSocket notification error: {e}")


def format_object_fields(obj):
    """
    Recursively convert UUID fields to strings and datetime fields to ISO format within an object.

    Args:
        obj (dict or list): The object to format (can be a dictionary or a list).

    Returns:
        dict or list: The formatted object with UUIDs as strings and datetimes as ISO strings.
    """
    if isinstance(obj, dict):
        formatted_obj = {}
        for key, value in obj.items():
            if isinstance(value, uuid.UUID):
                formatted_obj[key] = str(value)
            elif isinstance(value, datetime):
                formatted_obj[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                formatted_obj[key] = format_object_fields(value)
            else:
                formatted_obj[key] = value
        return formatted_obj

    elif isinstance(obj, list):
        return [format_object_fields(item) for item in obj]

    return obj