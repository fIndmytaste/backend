from django.core.management.base import BaseCommand
from account.models import Vendor

class Command(BaseCommand):
    help = 'List all vendors (not just marketplace vendors).'

    def handle(self, *args, **options):
        vendors = Vendor.objects.all()
        if not vendors:
            self.stdout.write(self.style.WARNING('No vendors found.'))
            return
        self.stdout.write(self.style.SUCCESS('All Vendors:'))
        for vendor in vendors:
            self.stdout.write(f"- {vendor.name} (Email: {vendor.email}) is_marketplace={vendor.is_marketplace}")
