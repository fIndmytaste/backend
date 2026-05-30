"""
Keeps the Redis geo index in sync whenever a Vendor record changes.

Rules:
  - Vendor is approved + active + has coordinates  →  GEOADD  (add/update)
  - Vendor is deactivated, rejected, or loses coords  →  ZREM  (remove)

This means populate_redis_geo only needs to run once on first deploy;
after that the index stays current automatically.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from account.models import Vendor
from helpers.redis_geo import geo_add_vendor, geo_remove_vendor


def _should_be_in_geo_index(vendor: Vendor) -> bool:
    return (
        vendor.approval_status == 'approved'
        and vendor.is_active
        and vendor.location_latitude
        and vendor.location_longitude
    )


@receiver(post_save, sender=Vendor)
def sync_vendor_geo(sender, instance: Vendor, **kwargs):
    """Add or remove the vendor from Redis geo index on every save."""
    try:
        if _should_be_in_geo_index(instance):
            geo_add_vendor(instance)
        else:
            geo_remove_vendor(str(instance.id))
    except Exception:
        # Never let a Redis failure crash a vendor save
        pass


@receiver(post_save, sender='product.BukaItemServiceCharge')
def lock_vendor_on_first_admin_pricing(sender, instance, created, **kwargs):
    """
    Auto-lock a vendor from creating new products once the admin sets
    pricing on any of their products, but only if the vendor's category
    is configured to lock after approval (e.g. Eatery, Buka).

    Idempotent: only flips the lock when it is currently False.
    """
    if not created:
        return

    vendor = instance.vendor or getattr(instance.product, 'vendor', None)
    if vendor is None:
        return

    category = vendor.category
    if category is None or not category.lock_products_after_approval:
        return

    if vendor.product_creation_locked:
        return

    Vendor.objects.filter(pk=vendor.pk, product_creation_locked=False).update(
        product_creation_locked=True
    )
