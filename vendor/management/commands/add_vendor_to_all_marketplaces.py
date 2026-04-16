from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from vendor.models import MarketPlace
from account.models import Vendor
from product.models import SystemCategory, Product, ProductImage
import json

User = get_user_model()

# You can reuse the upload_realistic_products function from add_complex_vendor.py

def upload_realistic_products(vendor, system_category=None, vendor_category=None, count=5):
    sample_products = [
        {
            'name': 'Premium Basmati Rice',
            'description': 'Long grain, aromatic basmati rice perfect for jollof and fried rice.',
            'price': 12000,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSJCn-xpn4sLh1Ktu_blViPQJOmVN9ZzkXNcQ&s',
        },
        {
            'name': 'Golden Cooking Oil (5L)',
            'description': 'High-quality vegetable oil for all your frying and cooking needs.',
            'price': 8500,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSDMLsP700PC2loYoXTgMSubsFoRkBm5fBlsQ&s',
        },
        {
            'name': 'Peak Full Cream Milk Powder',
            'description': 'Rich and creamy milk powder, 400g tin.',
            'price': 2500,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTgsLS6jBOfff4t3AOFYX8sG6_GmkTI23MZjw&s',
        },
        {
            'name': 'Indomie Instant Noodles (40 pack)',
            'description': 'Family pack of classic Indomie noodles, chicken flavor.',
            'price': 6500,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRssYtGRrgbgBXQOCkjv3EUWkdH-YaA5_LKEQ&s',
        },
        {
            'name': 'Heinz Baked Beans',
            'description': 'Delicious baked beans in tomato sauce, 415g can.',
            'price': 900,
            'image_url': 'https://seamart.com.ng/wp-content/uploads/2024/12/x693a-1.jpg',
        },
    ]
    for prod in sample_products[:count]:
        product = Product.objects.create(
            name=prod['name'],
            description=prod['description'],
            price=prod['price'],
            stock=100,
            vendor=vendor,
            system_category=system_category,
            category=vendor_category,
            is_active=True,
        )
        ProductImage.objects.create(
            product=product,
            image_url=prod['image_url'],
            is_primary=True
        )

class Command(BaseCommand):
    help = 'Add a realistic vendor to ALL marketplaces with sample products.'

    def handle(self, *args, **options):
        marketplaces = MarketPlace.objects.all()
        if not marketplaces:
            self.stdout.write(self.style.ERROR('No marketplaces found.'))
            return

        # Use a unique email for each vendor per marketplace
        for i, marketplace in enumerate(marketplaces, start=1):
            vendor_email = f"market_vendor_{i}@example.com"
            vendor_name = f"Market Vendor {i}"
            data = {
                'name': vendor_name,
                'email': vendor_email,
                'phone_number': f'+23480123456{i:03d}',
                'address': f'{i} Market Street, Lagos',
                'description': f'Realistic vendor for {marketplace.name}',
                'thumbnail_url': 'https://www.apprenticeship.ng/wp-content/uploads/2020/04/groceries.jpg',
                'is_marketplace': True,
                'is_active': True,
                'approval_status': 'approved',
            }
            user, _ = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'full_name': data['name'],
                    'role': 'vendor',
                    'is_active': True
                }
            )
            category = SystemCategory.objects.first()
            vendor, _ = Vendor.objects.update_or_create(
                user=user,
                defaults={
                    'name': data['name'],
                    'email': data['email'],
                    'phone_number': data['phone_number'],
                    'address': data['address'],
                    'description': data['description'],
                    'thumbnail_url': data['thumbnail_url'],
                    'is_marketplace': data['is_marketplace'],
                    'is_active': data['is_active'],
                    'approval_status': data['approval_status'],
                    'category': category
                }
            )
            if vendor not in marketplace.vendors.all():
                marketplace.vendors.add(vendor)
                marketplace.save()
            upload_realistic_products(vendor, system_category=category)
            self.stdout.write(self.style.SUCCESS(f"Vendor '{vendor.name}' added to marketplace '{marketplace.name}'."))
