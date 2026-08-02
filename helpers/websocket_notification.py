from typing import Optional
from channels.layers import get_channel_layer
from account.models import Rider
from asgiref.sync import async_to_sync
from django.db.models import Count, Q
from django.utils import timezone
import logging
import uuid
from datetime import datetime, timedelta

from helpers.order_utils import get_distance_between_two_location
from helpers.redis_rider_geo import (
    RIDER_GEO_FRESHNESS_SECONDS,
    geo_nearby_rider_ids,
)
from product.models import Order
from helpers.push_notification import notification_helper
from rider.serializers import OrderSerializer

logger = logging.getLogger(__name__)

ORDER_DISPATCH_RADIUS_STEPS_KM = (
    (30, 15),
    (120, 25),
    (float("inf"), 35),
)
ORDER_DISPATCH_NEIGHBOURHOOD_RADII_KM = (3, 8, 15, 25, 35)


def get_order_dispatch_radius_km(order: Order) -> int:
    anchor_time = order.created_at or order.updated_at or timezone.now()
    age_seconds = max(0, (timezone.now() - anchor_time).total_seconds())
    for max_age_seconds, radius_km in ORDER_DISPATCH_RADIUS_STEPS_KM:
        if age_seconds <= max_age_seconds:
            return radius_km
    return 35


def _get_rider_dispatch_coordinates(rider: Rider):
    latitude = rider.current_latitude or rider.location_latitude
    longitude = rider.current_longitude or rider.location_longitude
    if latitude is None or longitude is None:
        return None
    return float(latitude), float(longitude)


def _dispatch_neighbourhood_index(distance_km: float, max_radius_km: int) -> int:
    for index, radius in enumerate(ORDER_DISPATCH_NEIGHBOURHOOD_RADII_KM):
        if radius >= max_radius_km:
            return index if distance_km <= max_radius_km else len(ORDER_DISPATCH_NEIGHBOURHOOD_RADII_KM)
        if distance_km <= radius:
            return index
    return len(ORDER_DISPATCH_NEIGHBOURHOOD_RADII_KM)


def _get_dispatch_search_radii(max_radius_km: int) -> list[float]:
    radii = [radius for radius in ORDER_DISPATCH_NEIGHBOURHOOD_RADII_KM if radius <= max_radius_km]
    if not radii or radii[-1] != max_radius_km:
        radii.append(max_radius_km)
    return radii


def is_order_visible_to_rider(
    order: Order,
    rider: Rider,
    *,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> bool:
    if rider.status != 'active' or not rider.is_verified or not rider.is_online:
        return False

    if rider.declined_orders.filter(order_id=order.id).exists():
        return False

    coords = (
        (latitude, longitude)
        if latitude is not None and longitude is not None
        else _get_rider_dispatch_coordinates(rider)
    )
    if coords is None:
        return False

    try:
        distance = get_distance_between_two_location(
            lat1=float(coords[0]),
            lon1=float(coords[1]),
            lat2=float(order.vendor.location_latitude),
            lon2=float(order.vendor.location_longitude),
        )
    except (TypeError, ValueError):
        return False

    return distance is not None and distance <= get_order_dispatch_radius_km(order)


def get_candidate_riders_for_order(order: Order, exclude_rider: Optional[Rider] = None):
    """
    Return riders eligible to see an available order based on proximity and status,
    ordered by expanding neighbourhood bands around the vendor.
    Marketplace vendor orders are excluded — they require admin assignment.
    """
    vendor = order.vendor
    if getattr(vendor, 'is_marketplace', False) or vendor.marketplace_set.exists():
        return []

    riders = Rider.objects.filter(
        status='active',
        is_verified=True,
        is_online=True,
    ).select_related('user').annotate(
        active_assignment_count=Count(
            'orders',
            filter=Q(orders__status__in=['rider_assigned', 'picked_up', 'in_transit', 'near_delivery']),
            distinct=True,
        )
    )

    max_radius_km = get_order_dispatch_radius_km(order)
    search_radii = _get_dispatch_search_radii(max_radius_km)
    nearby_geo_ids = geo_nearby_rider_ids(
        float(order.vendor.location_latitude),
        float(order.vendor.location_longitude),
        search_radii,
    )

    if nearby_geo_ids is not None:
        stale_before = timezone.now() - timedelta(seconds=RIDER_GEO_FRESHNESS_SECONDS)
        ordered_ids = [rider_id for rider_id, _ in nearby_geo_ids]
        riders_by_id = {
            str(r.id): r
            for r in riders.filter(
                id__in=ordered_ids,
                location_updated_at__gte=stale_before,
            )
        }

        candidates = []
        for rider_id, distance in nearby_geo_ids:
            rider = riders_by_id.get(rider_id)
            if rider is None:
                continue
            if exclude_rider is not None and rider.id == exclude_rider.id:
                continue
            if not is_order_visible_to_rider(order, rider):
                continue
            candidates.append(rider)
        logger.debug(
            "Rider dispatch using Redis geo for order %s: radius=%skm nearby=%s eligible=%s",
            order.id,
            max_radius_km,
            len(nearby_geo_ids),
            len(candidates),
        )
        if candidates:
            return candidates
        logger.debug(
            "Redis returned no eligible riders for order %s; falling back to DB scan",
            order.id,
        )

    candidates = []
    for rider in riders:
        if exclude_rider is not None and rider.id == exclude_rider.id:
            continue

        if rider.declined_orders.filter(order_id=order.id).exists():
            continue

        coords = _get_rider_dispatch_coordinates(rider)
        if coords is None:
            continue

        try:
            distance = get_distance_between_two_location(
                lat1=coords[0],
                lon1=coords[1],
                lat2=float(order.vendor.location_latitude),
                lon2=float(order.vendor.location_longitude),
            )
        except (TypeError, ValueError):
            continue

        if distance is None or distance > max_radius_km:
            continue

        candidates.append(
            (
                _dispatch_neighbourhood_index(distance, max_radius_km),
                distance,
                rider,
            )
        )

    candidates.sort(key=lambda item: (item[0], item[1]))
    logger.debug(
        "Rider dispatch fallback DB scan for order %s: radius=%skm eligible=%s",
        order.id,
        max_radius_km,
        len(candidates),
    )
    return [rider for _, _, rider in candidates]


def notify_order_unavailable_to_riders(order: Order, accepted_rider: Optional[Rider] = None):
    """
    Remove an accepted order from every other rider that could still see it.
    """
    channel_layer = get_channel_layer()
    for rider in get_candidate_riders_for_order(order, exclude_rider=accepted_rider):
        try:
            async_to_sync(channel_layer.group_send)(
                f"riders_group_{rider.user.id}",
                {
                    "type": "order_accepted_notification",
                    "data": {
                        "order_id": str(order.id),
                        "track_id": str(order.track_id),
                        "status": str(order.status),
                        "delivery_status": str(order.delivery_status),
                        "message": "This order has been accepted by another rider.",
                    },
                },
            )
        except Exception as e:
            print(f"Order unavailable websocket notification error: {e}")


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
            "near_delivery": "Your rider is outside and waiting for you.",
            "delivered": "Your order has been delivered. Enjoy!",
            "cancelled": "Your order has been cancelled.",
        }
        message = default_messages.get(status, "Order status updated.")
    
    try:
        notification_helper.send_to_user_async(
            user=order.user,
            title=f"Order {status.capitalize()}!",
            body=message,
            data={
                "type": "order_status_update",
                "order_id": str(order.id),
                "status": status,
            }
        )
    except Exception as e:
        print(f"Push notification error: {e}")


def notify_rider_order_assignment(order: Order, rider: Rider, message: Optional[str] = None):
    """
    Notify a specific rider that an order has been assigned to them.
    """
    body = message or (
        f"You have been assigned order #{order.track_id}. "
        "Please proceed to the vendor for pickup."
    )
    payload = {
        "event": "order_assigned",
        "order_id": str(order.id),
        "track_id": str(order.track_id),
        "status": str(order.status),
        "delivery_status": str(order.delivery_status),
    }

    try:
        notification_helper.send_to_user_async(
            user=rider.user,
            title="New Order Assigned!",
            body=body,
            data=payload,
        )
    except Exception as e:
        print(f"Rider assignment push notification error: {e}")

    try:
        channel_layer = get_channel_layer()
        rider_group_name = f"riders_group_{rider.user.id}"
        async_to_sync(channel_layer.group_send)(
            rider_group_name,
            {
                "type": "order_assigned_notification",
                "data": {
                    "order_id": str(order.id),
                    "track_id": str(order.track_id),
                    "status": str(order.status),
                    "delivery_status": str(order.delivery_status),
                    "vendor": {
                        "name": order.vendor.name,
                        "location": {
                            "latitude": order.vendor.location_latitude,
                            "longitude": order.vendor.location_longitude,
                        },
                    },
                    "customer": {
                        "name": order.user.full_name,
                        "location": {
                            "latitude": order.delivery_latitude,
                            "longitude": order.delivery_longitude,
                        },
                    },
                    "assigned_at": timezone.now().isoformat(),
                    "message": body,
                },
            },
        )
    except Exception as e:
        print(f"Rider assignment websocket notification error: {e}")



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

        # Notify all currently eligible nearby riders, not just the closest one.
        for rider in get_candidate_riders_for_order(order):
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
                            'track_id': str(order.track_id),
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
                title="Order Accepted!",
                body=f"Your order has been accepted by the vendor. Preparing your order now!",
                data={
                    "type": "order_status_update",
                    "order_id": str(order.id),
                    "status": "confirmed",
                }
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
