from django.core.management.base import BaseCommand
from django.db import IntegrityError
from decimal import Decimal
from account.models import User, Vendor
from product.models import Product, SystemCategory, VendorCategory

class Command(BaseCommand):
    help = 'Creates a single vendor, assigns a vendor category, and adds 10 products to the vendor.'

    def handle(self, *args, **kwargs):

        user_data = {
            'first_name': 'John',
            "username":"username",
            'last_name': 'Doe',
            'email': 'vendor1@example.com',
            'phone_number': '1234567890',
        }




        # Vendor details
        vendor_data = {
            'name': 'Vendor One',
            'email': 'vendor1@example.com',
            'phone_number': '1234567890',
            'address': '123 Street, City, Country',
            'description': 'Vendor One Description',
            'category': 'Restaurant'
        }



        # Vendor categories (this can be extended as needed)
        vendor_categories_data = [
            {'name': 'Restaurant', 'description': 'Restaurant vendor category.'}
        ]
        
        # Create System Categories if not exist
        system_categories_data = [
            {'name': 'Food', 'description': 'Food related items.'},
            {'name': 'Health', 'description': 'Health related items.'}
        ]

        
        for system_category_data in system_categories_data:
            if not SystemCategory.objects.filter(name=system_category_data['name']).exists():
                SystemCategory.objects.create(**system_category_data)
                self.stdout.write(self.style.SUCCESS(f"Created system category: {system_category_data['name']}"))

        
        user = User.objects.create(**user_data)
        user.set_password("password123")
        user.save()

        created_vendor = None
        if not Vendor.objects.filter(email=vendor_data['email']).exists():
            # First, create the vendor
            created_vendor = Vendor.objects.create(
                name=vendor_data['name'],
                email=vendor_data['email'],
                user=user,
                phone_number=vendor_data['phone_number'],
                address=vendor_data['address'],
                description=vendor_data['description'],
            )

            created_vendor.category = SystemCategory.objects.first()
            created_vendor.save()

            self.stdout.write(self.style.SUCCESS(f"Created vendor: {vendor_data['name']}"))


        
        # Create Vendor Categories
        for vendor_category_data in vendor_categories_data:
            if not VendorCategory.objects.filter(name=vendor_category_data['name']).exists():
                vendor_category = VendorCategory.objects.create(**vendor_category_data, vendor=created_vendor)
                self.stdout.write(self.style.SUCCESS(f"Created vendor category: {vendor_category_data['name']}"))

            # Create Products for Vendor
            for i in range(1, 11):  # Create 10 products for the vendor
                product_data = {
                    'name': f"Product {i} for {vendor_data['name']}",
                    'description': f"A description for Product {i} from {vendor_data['name']}",
                    'price': Decimal('19.99'),
                    'system_category': SystemCategory.objects.get(name='Food'), 
                    'category': vendor_category,  
                    'stock': 100,
                    'vendor': created_vendor
                }
                product = Product.objects.create(**product_data)
                self.stdout.write(self.style.SUCCESS(f"Created product: {product.name}"))
        else:
            self.stdout.write(self.style.WARNING(f"Vendor {vendor_data['name']} already exists"))
