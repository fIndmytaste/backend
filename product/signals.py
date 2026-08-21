"""Order signals."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from product.models import Order
from product.vendor_notifications import notify_vendor_of_paid_order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def alert_vendor_when_order_is_paid(sender, instance: Order, **kwargs):
    """Tell the vendor as soon as an order is actually paid for.

    Hooking the paid state rather than a particular checkout view means link
    payments -- the majority of orders -- raise the alert too. The helper is
    idempotent, so the repeated saves an order goes through cannot produce
    duplicate alerts.
    """
    if instance.payment_status != 'paid':
        return
    try:
        notify_vendor_of_paid_order(instance)
    except Exception:
        # An alert must never roll back or break a payment.
        logger.exception("Vendor alert failed for order %s", instance.pk)
