from django.core.management.base import BaseCommand, CommandError
from vendor.models import MarketPlace

class Command(BaseCommand):
    help = 'List all vendors belonging to a given marketplace by ID, or all marketplaces if no ID is provided.'

    def add_arguments(self, parser):
        parser.add_argument('--marketplace_id', type=str, help='Marketplace UUID (optional)', nargs='?')

    def handle(self, *args, **options):
        marketplace_id = options.get('marketplace_id')
        if marketplace_id:
            try:
                marketplace = MarketPlace.objects.get(id=marketplace_id)
                vendors = marketplace.vendors.all()
                self.stdout.write(self.style.SUCCESS(f"Vendors for marketplace '{marketplace.name}':"))
                for vendor in vendors:
                    self.stdout.write(f"- {vendor.name} (Email: {vendor.email})")
            except MarketPlace.DoesNotExist:
                raise CommandError('Marketplace not found.')
        else:
            marketplaces = MarketPlace.objects.all()
            if not marketplaces:
                self.stdout.write(self.style.WARNING('No marketplaces found.'))
                return
            for marketplace in marketplaces:
                vendors = marketplace.vendors.all()
                self.stdout.write(self.style.SUCCESS(f"\nVendors for marketplace '{marketplace.name}':"))
                if vendors:
                    for vendor in vendors:
                        self.stdout.write(f"- {vendor.name} (Email: {vendor.email})")
                else:
                    self.stdout.write("  No vendors found.")
