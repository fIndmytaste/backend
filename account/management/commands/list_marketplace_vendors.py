from django.core.management.base import BaseCommand
from account.models import Vendor

class Command(BaseCommand):
    help = 'List all vendors where is_marketplace=True.'

    def handle(self, *args, **options):
        vendors = Vendor.objects.filter(is_marketplace=True)
        if not vendors:
            self.stdout.write(self.style.WARNING('No marketplace vendors found.'))
            return
        self.stdout.write(self.style.SUCCESS('Marketplace Vendors:'))
        for vendor in vendors:
            self.stdout.write(f"- {vendor.name} (Email: {vendor.email})")
