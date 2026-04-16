# your_app/management/commands/add_lagos_marketplaces.py

from django.core.management.base import BaseCommand

from vendor.models import MarketPlace

class Command(BaseCommand):
    help = 'Add popular marketplaces in Lagos to the MarketPlace model.'

    def handle(self, *args, **options):
        for ven in MarketPlace.objects.all():
            print(ven.vendors.all())


        return




        return
        marketplaces = [
            {"name": "Oyingbo", "description": "Popular market in Lagos mainland."},
            {"name": "Ojota", "description": "Bustling transport and market hub."},
            {"name": "Mile 12", "description": "Known for food and produce trading."},
            {"name": "Tejuosho", "description": "Modern shopping complex in Yaba."},
            {"name": "Balogun", "description": "Busy market on Lagos Island."},
            {"name": "Computer Village", "description": "Electronics & tech market in Ikeja."},
        ]

        for market in marketplaces:
            obj, created = MarketPlace.objects.get_or_create(
                name=market['name'],
                defaults={
                    'description': market['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created market: {market['name']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Market already exists: {market['name']}"))
