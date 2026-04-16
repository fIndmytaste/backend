from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from vendor.models import MarketPlace
from account.models import Vendor
from product.models import SystemCategory
import json
from product.models import Product, ProductImage

User = get_user_model()


def upload_realistic_products(vendor, system_category=None, vendor_category=None, count=10):
    """
    Create and upload multiple realistic products for a gourmet food/provisions vendor.
    """
    Product.objects.filter(vendor=vendor).delete()  # Clear existing products for this vendor

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
        {
            'name': 'Honeywell Wheat Flour (2kg)',
            'description': 'Premium wheat flour for baking and swallow.',
            'price': 2200,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRY7y0Px5ICTa6aG8C794nP8FhZgEPx2avy2A&s',
        },
        {
            'name': 'Frozen Chicken Drumsticks (1kg)',
            'description': 'Fresh frozen chicken drumsticks, ready to cook.',
            'price': 3500,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR6sGDbWH-x29yzRrj1Z95OE5sEvZcTScoNbA&s',
        },
        {
            'name': 'Dano Yogurt Drink (Strawberry, 1L)',
            'description': 'Refreshing strawberry yogurt drink, 1 litre.',
            'price': 1200,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSiySzqXv6G6WjSgzSP1IUeKxn3_ts7KNwQTA&s',
        },
        {
            'name': 'Kings Vegetable Oil (1L)',
            'description': 'Affordable and healthy vegetable oil for everyday use.',
            'price': 1800,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ5V9cgftcLedyXpN13_xZaIY-DKjRA6K-Rhw&s',
        },
        {
            'name': 'Gino Tomato Paste (210g)',
            'description': 'Rich tomato paste for stews and sauces.',
            'price': 400,
            'image_url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQsttAHd38OL4GKmM2tl2u7o5Gl7gsOEr3A0g&s',
        },
    ]

    
    for i, prod in enumerate(sample_products[:count]):
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

    # help = 'Add a vendor to a marketplace with full details using a hardcoded dictionary.'

    # Hardcoded vendor details
    VENDOR_DATA = {
        'name': 'Cornerstone Provisions',
        'email': 'oyingbo_gourmet@example.com',
        'phone_number': '+2348012345678',
        'address': '123 Market Street, Oyingbo, Lagos',
        'description': 'Premium gourmet food vendor in Oyingbo Market.',
        'marketplace_name': 'Oyingbo',
        'category_name': 'Eatery',
        'thumbnail_url': 'https://example.com/thumbnails/oyingbo_gourmet.jpg',
        'is_marketplace': True,
        'is_active': True,
        'approval_status': 'approved'
    }

    def handle(self, *args, **options):

        vendor = Vendor.objects.filter(user__email='oyingbo_gourmet@example.com').first()
        if vendor:
            self.stdout.write(
                self.style.WARNING(
                    f"Vendor with email '{self.VENDOR_DATA['email']}' already exists. No new vendor created."
                )
            )

            vendor.city = 'Lagos'
            vendor.name = 'Cornerstone Provisions'
            vendor.state = 'Lagos State'
            vendor.country = 'Nigeria'

            vendor.description ='Your one-stop provision store at Oyingbo Market. We offer a wide range of quality groceries, staples, and everyday essentials at affordable prices.'
            vendor.thumbnail_url = 'https://www.apprenticeship.ng/wp-content/uploads/2020/04/groceries.jpg'
            vendor.logo_url = 'https://www.apprenticeship.ng/wp-content/uploads/2020/04/groceries.jpg'
            vendor.close_day = 'Sunday'
            vendor.bank_account = '1234567890'
            vendor.bank_account_name = 'Cornerstone Provisions'
            vendor.bank_name = 'First Bank'
            vendor.save()

            user = vendor.user
            user.is_verified = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Vendor '{vendor.name}' updated with location details."))

            # Upload realistic products for this vendor
            upload_realistic_products(vendor, system_category=vendor.category)
            return
        
        # return
        data = self.VENDOR_DATA
        
        # 1. Handle User
        user, created = User.objects.get_or_create(
            email=data['email'],
            defaults={
                'full_name': data['name'],
                'role': 'vendor',
                'is_active': True
            }
        )
        if created:
            user.set_password('temporary_password_123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f"User created for {data['email']}"))
        else:
            self.stdout.write(f"Using existing user for {data['email']}")

        # 2. Handle Marketplace
        try:
            marketplace = MarketPlace.objects.get(name__iexact=data['marketplace_name'])
        except MarketPlace.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Marketplace '{data['marketplace_name']}' not found."))
            return

        # 3. Handle Category
        category = None
        if data.get('category_name'):
            try:
                category = SystemCategory.objects.get(name__iexact=data['category_name'])
            except SystemCategory.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Category '{data['category_name']}' not found. Vendor will have no category."))

        # 4. Create/Update Vendor
        vendor, created = Vendor.objects.update_or_create(
            user=user,
            defaults={
                'name': data['name'],
                'email': data['email'],
                'phone_number': data['phone_number'],
                'address': data['address'],
                'description': data['description'],
                'thumbnail_url': data.get('thumbnail_url', ''),
                'is_marketplace': data.get('is_marketplace', False),
                'is_active': data.get('is_active', True),
                'approval_status': data.get('approval_status', 'pending'),
                'category': category
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"Vendor '{data['name']}' created successfully."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Vendor '{data['name']}' updated successfully."))

        # 5. Add Vendor to Marketplace
        if vendor not in marketplace.vendors.all():
            marketplace.vendors.add(vendor)
            marketplace.save()
            self.stdout.write(self.style.SUCCESS(f"Vendor added to {data['marketplace_name']} marketplace."))

        # Output basic vendor data
        vendor_info = {
            'id': str(vendor.id),
            'name': vendor.name,
            'email': vendor.email,
            'category': str(vendor.category) if vendor.category else None,
            'marketplace': marketplace.name
        }
        self.stdout.write(json.dumps(vendor_info, indent=2))
