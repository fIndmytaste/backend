from django.core.management.base import BaseCommand
from vendor.models import MarketPlace

class Command(BaseCommand):
    help = 'Get all vendors in all MarketPlaces'

    def handle(self, *args, **options):
        marketplaces = MarketPlace.objects.all()
        if not marketplaces:
            self.stdout.write(self.style.WARNING('No MarketPlaces found.'))
            return
        import json
        for marketplace in marketplaces:
            self.stdout.write(self.style.SUCCESS(f'MarketPlace: {getattr(marketplace, "name", str(marketplace.id))}'))
            vendors = marketplace.vendors.all()
            if not vendors:
                self.stdout.write('  No vendors in this MarketPlace.')
            for vendor in vendors:
                vendor_data = {
                    'id': vendor.id,
                    'name': getattr(vendor, 'name', 'N/A'),
                    'email': getattr(vendor, 'email', 'N/A'),
                    'description': getattr(vendor, 'description', ''),
                    'phone': getattr(vendor, 'phone', ''),
                    'address': getattr(vendor, 'address', ''),
                    'thumbnail': vendor.thumbnail.url if hasattr(vendor, 'thumbnail') and vendor.thumbnail else '',
                }
                print(vendor.user)
                user = vendor.user
                user.set_password('oyingbo123')
                user.save()
                print(vendor_data)
                # self.stdout.write(json.dumps(vendor_data, ensure_ascii=False, indent=2))
                # vendor.delete()
