"""
How much of the order book a marketplace staff member is allowed to see.

Paystack settles a collection into our balance roughly 24 hours after the
customer pays. Until then the order's money is not ours to act on, so
marketplace staff work a deliberately delayed view of the order book: an order
only becomes visible to them once it is older than
STAFF_ORDER_VISIBILITY_HOURS.

The delay is on *visibility*, not on the data — once an order appears, staff
see its true placement date and time, so they can still correlate it against
the market's own records. Superusers and full admins are never delayed; they
see every order the moment it is placed.
"""

from datetime import timedelta

from django.utils import timezone

STAFF_ORDER_VISIBILITY_HOURS = 24


def staff_order_visibility_cutoff(now=None):
    """Orders created after this moment are not yet visible to staff."""
    return (now or timezone.now()) - timedelta(hours=STAFF_ORDER_VISIBILITY_HOURS)


def limit_orders_to_visible_window(queryset, now=None):
    """Drop orders that are still inside the settlement window."""
    return queryset.filter(created_at__lte=staff_order_visibility_cutoff(now))
