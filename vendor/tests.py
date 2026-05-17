from django.test import TestCase

from account.models import User, Vendor
from helpers.vendor_discovery import local_vendor_queryset
from product.models import SystemCategory
from vendor.models import MarketPlace


class LocalVendorQuerysetTests(TestCase):
    def setUp(self):
        self.category = SystemCategory.objects.create(
            name="Food",
            name_key="food",
            description="Food vendors",
        )

    def create_vendor(self, email, **kwargs):
        user = User.objects.create_user(
            email=email,
            password="password",
            role="vendor",
        )
        defaults = {
            "user": user,
            "name": email.split("@")[0],
            "email": email,
            "category": self.category,
            "approval_status": "approved",
            "is_active": True,
        }
        defaults.update(kwargs)
        return Vendor.objects.create(**defaults)

    def test_excludes_marketplace_flagged_and_marketplace_members(self):
        local_vendor = self.create_vendor("local@example.com")
        flagged_vendor = self.create_vendor("flagged@example.com", is_marketplace=True)
        member_vendor = self.create_vendor("member@example.com")
        inactive_marketplace_member = self.create_vendor("inactive-member@example.com")

        active_marketplace = MarketPlace.objects.create(name="Balogun", is_active=True)
        active_marketplace.vendors.add(member_vendor)

        inactive_marketplace = MarketPlace.objects.create(name="Old Market", is_active=False)
        inactive_marketplace.vendors.add(inactive_marketplace_member)

        vendors = set(local_vendor_queryset())

        self.assertIn(local_vendor, vendors)
        self.assertIn(inactive_marketplace_member, vendors)
        self.assertNotIn(flagged_vendor, vendors)
        self.assertNotIn(member_vendor, vendors)
