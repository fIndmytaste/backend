"""Vendor alert for an order that has just been paid for.

This used to live inline inside the two customer checkout views, nested under
`if order.payment_method == 'wallet'`. Wallet is the minority payment method --
most customers pay by link -- so the vendor was never told about the majority
of their orders. Centralising it here means the alert follows the order
becoming paid, whichever code path gets it there.
"""

import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)

VENDOR_NEW_ORDER_TITLE = "New Order Received!"


def _customer_name(order):
    user = order.user
    if not user:
        return "a customer"
    return (
        user.full_name
        or f"{user.first_name or ''} {user.last_name or ''}".strip()
        or user.email
    )


def already_notified(order, vendor_user_id):
    """True when this vendor has already been alerted about this order.

    Notification has no order FK, so the track id in the body is what ties a
    row to its order. Keeps the alert idempotent no matter how many times the
    order is saved after payment.
    """
    from account.models import Notification

    track_id = str(order.track_id or order.id)
    return Notification.objects.filter(
        user_id=vendor_user_id,
        title=VENDOR_NEW_ORDER_TITLE,
        content__icontains=track_id,
    ).exists()


def notify_vendor_of_paid_order(order):
    """Websocket event, in-app row and push, for a newly paid order.

    Every step is individually guarded: a vendor with no device token, or a
    websocket layer that is down, must not stop the others from landing.
    """
    from account.models import Notification
    from helpers.push_notification import notification_helper
    from product.serializers import OrderSerializer

    vendor = order.vendor
    if vendor is None or not vendor.user_id:
        return
    if already_notified(order, vendor.user_id):
        return

    customer = _customer_name(order)
    track_id = str(order.track_id or order.id)

    try:
        # The channel layer can only carry JSON primitives. A DRF .data still
        # holds UUID objects (order.user and each item's product id), and
        # group_send raises on them -- which silently cost the vendor their
        # in-app new-order alert, since the failure is caught below while the
        # notification row and push carried on regardless. Round-tripping
        # through DjangoJSONEncoder flattens them to strings.
        order_details = json.loads(
            json.dumps(OrderSerializer(order).data, cls=DjangoJSONEncoder)
        )
        async_to_sync(get_channel_layer().group_send)(
            f'vendor_{vendor.user_id}',
            {
                'type': 'new_order_notification',
                'data': {
                    'order_id': str(order.id),
                    'track_id': track_id,
                    'customer': {
                        'name': customer,
                        'phone': order.user.phone_number if order.user else None,
                    },
                    "order_details": order_details,
                    'delivery_address': order.address,
                    'created_at': order.created_at.isoformat() if order.created_at else None,
                    'status': order.status,
                },
            },
        )
    except Exception:
        logger.exception("Vendor websocket alert failed for order %s", order.id)

    try:
        Notification.objects.create(
            user=vendor.user,
            title=VENDOR_NEW_ORDER_TITLE,
            content=(
                f"You have a new order #{track_id} from {customer}. "
                "Tap to review and accept."
            ),
        )
    except Exception:
        logger.exception("Vendor in-app alert failed for order %s", order.id)

    try:
        notification_helper.send_to_user_async(
            user=vendor.user,
            title="New Order Received! 🛎️",
            body=f"Order #{track_id} from {customer}. Tap to review and accept.",
            data={
                "event": "new_order",
                "type": "new_order_notification",
                "order_id": str(order.id),
                "track_id": track_id,
            },
        )
    except Exception:
        logger.exception("Vendor push alert failed for order %s", order.id)
