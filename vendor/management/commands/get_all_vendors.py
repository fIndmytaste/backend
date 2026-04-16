from django.core.management.base import BaseCommand
from vendor.models import Vendor

class Command(BaseCommand):
    help = 'Get all marketplace vendors'

    def handle(self, *args, **options):
        vendors = Vendor.objects.all()
        if not vendors:
            self.stdout.write(self.style.WARNING('No vendors found.'))
            return
        for vendor in vendors:
            self.stdout.write(f'ID: {vendor.id}, Name: {getattr(vendor, "name", "N/A")}, Email: {getattr(vendor, "email", "N/A")}')
