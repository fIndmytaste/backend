import random
import uuid
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.utils.timezone import now

from vendor.models import MarketPlace
from account.models import Vendor, Address  
from product.models import SystemCategory 

User = get_user_model()

# Marketplaces with approximate lat/lng
MARKETPLACES = [
    {"name": "Oyingbo", "description": "Popular market in Lagos mainland.", "lat": "6.4726", "lng": "3.3792"},
    {"name": "Ojota", "description": "Bustling transport and market hub.", "lat": "6.5890", "lng": "3.3790"},
    {"name": "Mile 12", "description": "Known for food and produce trading.", "lat": "6.6018", "lng": "3.3934"},
    {"name": "Tejuosho", "description": "Modern shopping complex in Yaba.", "lat": "6.5095", "lng": "3.3785"},
    {"name": "Balogun", "description": "Busy market on Lagos Island.", "lat": "6.4549", "lng": "3.3896"},
    {"name": "Computer Village", "description": "Electronics & tech market in Ikeja.", "lat": "6.6059", "lng": "3.3491"},
]

SAMPLE_CATEGORIES = [
    "Food",
    "Electronics",
    "Clothing",
    "Household",
    "Books",
]

class Command(BaseCommand):
    help = 'Add Lagos marketplaces with vendors, including lat/lng data.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Creating marketplaces and vendors..."))


        cat = SystemCategory.objects.filter(name="Marketplace").first()
        if cat:
            
            marketplaces = MarketPlace.objects.all()
            for market in marketplaces:
                vendors = market.vendors.all()
                for vendor in vendors:
                    vendor.category = cat
                    vendor.is_marketplace = True
                    vendor.save()
                    print(vendor.name)



        return

        # Create categories
        categories = []
        for name in SAMPLE_CATEGORIES:
            cat, _ = SystemCategory.objects.get_or_create(name=name)
            # categories.append(cat)
            cat.delete()


        return

        for market in MARKETPLACES:
            lat, lng = market["lat"], market["lng"]

            # Create or get the marketplace
            marketplace, created = MarketPlace.objects.get_or_create(
                name=market["name"],
                defaults={"description": market["description"]}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✅ Created marketplace: {marketplace.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ Marketplace already exists: {marketplace.name}"))

            # Create 3 vendors
            for i in range(1, 4):
                unique_id = str(uuid.uuid4())[:8]
                email = f"{slugify(market['name'])}-vendor{i}-{unique_id}@example.com"
                full_name = f"{market['name']} Vendor {i}"

                # Create User
                user = User.objects.create_user(
                    email=email,
                    password="testpassword123",
                    full_name=full_name,
                    role="vendor",
                    is_active=True
                )

                # Create Vendor
                vendor = Vendor.objects.create(
                    user=user,
                    name=full_name,
                    email=email,
                    phone_number=f"080{random.randint(10000000,99999999)}",
                    country="Nigeria",
                    state="Lagos",
                    city=market["name"],
                    address=f"{market['name']} Market, Lagos",
                    location_latitude=lat,
                    location_longitude=lng,
                    description=f"Vendor {i} at {market['name']}",
                    is_active=True,
                    is_marketplace=True,
                    category=random.choice(categories),
                )

                # Create Address
                Address.objects.create(
                    user=user,
                    country="Nigeria",
                    state="Lagos",
                    city=market["name"],
                    address=f"{market['name']} Market Street, Lagos",
                    location_latitude=lat,
                    location_longitude=lng,
                    is_primary=True
                )

                # Assign vendor to marketplace
                marketplace.vendors.add(vendor)

                self.stdout.write(self.style.SUCCESS(
                    f"   🛒 Vendor '{vendor.name}' created with lat/lng ({lat}, {lng})"
                ))

        self.stdout.write(self.style.SUCCESS("🎉 Marketplaces and vendors created successfully."))
