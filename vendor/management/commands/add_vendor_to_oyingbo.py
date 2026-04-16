from django.core.management.base import BaseCommand
from product.models import User
from vendor.models import MarketPlace
from account.models import Vendor
from django.core.files.base import ContentFile

class Command(BaseCommand):
    help = 'Add a vendor to the Oyingbo marketplace with full details.'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, required=True, help='Vendor name')
        parser.add_argument('--email', type=str, required=True, help='Vendor email')
        parser.add_argument('--thumbnail_path', type=str, required=True, help='Path to vendor thumbnail image')
        parser.add_argument('--description', type=str, default='', help='Vendor description')
        parser.add_argument('--phone', type=str, default='', help='Vendor phone number')
        parser.add_argument('--address', type=str, default='', help='Vendor address')

    def handle(self, *args, **options):
        name = options['name']
        email = options['email']
        thumbnail_path = options['thumbnail_path']
        description = options['description']
        phone = options['phone']
        address = options['address']

        try:
            marketplace = MarketPlace.objects.get(name__iexact='Oyingbo')
        except MarketPlace.DoesNotExist:
            self.stdout.write(self.style.ERROR('Oyingbo marketplace not found.'))
            return
        
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create_user(email=email, password='defaultpassword123')
            self.stdout.write(self.style.SUCCESS(f'User account created for vendor "{name}" with email "{email}".'))

        #  create a user account for the vendor
        if Vendor.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'Vendor with email "{email}" already exists.'))
            return
        

        # Create Vendor
        vendor = Vendor(
            user=user,
            name=name,
            email=email,
            description=description,
            phone_number=phone,
            address=address,
            is_marketplace=True
        )
        # Add thumbnail
        try:
            with open(thumbnail_path, 'rb') as img_file:
                vendor.thumbnail.save(f'{name}_thumbnail.jpg', ContentFile(img_file.read()), save=False)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to add thumbnail: {e}'))

        vendor.save()
        marketplace.vendors.add(vendor)
        marketplace.save()

        import json
        vendor_data = {
            'id': vendor.id,
            'name': vendor.name,
            'email': vendor.email,
            'description': vendor.description,
            'phone': vendor.phone,
            'address': vendor.address,
            'thumbnail': vendor.thumbnail.url if hasattr(vendor, 'thumbnail') and vendor.thumbnail else '',
        }
        self.stdout.write(json.dumps(vendor_data, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS(f'Vendor "{name}" added to Oyingbo marketplace successfully.'))
