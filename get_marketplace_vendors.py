import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'findmytaste.settings')
django.setup()

from vendor.models import MarketPlace

# Replace with your marketplace ID or name
marketplace_id = '0aec0ac7-e48b-4da8-ac5e-aabfa6c46f34'

try:
    marketplace = MarketPlace.objects.get(id=marketplace_id)
    vendors = marketplace.vendors.all()
    print(f"Vendors for marketplace '{marketplace.name}':")
    for vendor in vendors:
        print(f"- {vendor.name} (Email: {vendor.email})")
except MarketPlace.DoesNotExist:
    print("Marketplace not found.")
