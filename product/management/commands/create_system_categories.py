from django.core.management.base import BaseCommand
from django.db import IntegrityError

from product.models import SystemCategory

class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        # List of predefined categories to add
        categories = [
            {'name': 'Restaurant', 'description': 'All kinds of restaurants'},
            {'name': 'Pharmacy', 'description': 'Pharmacies and medical stores'},
            {'name': 'Perfume Store', 'description': 'Stores selling perfumes and fragrances'},
            {'name': 'Cosmetic', 'description': 'Beauty products and cosmetics'},
            {'name': 'Market Place', 'description': 'Online marketplace for various goods'},
        ]

        for category in categories:
            name = category['name']
            description = category['description']
            # Check if the category already exists
            if not SystemCategory.objects.filter(name=name).exists():
                try:
                    # Create the category
                    SystemCategory.objects.create(name=name, description=description)
                    self.stdout.write(self.style.SUCCESS(f'Successfully added category: {name}'))
                except IntegrityError:
                    self.stdout.write(self.style.ERROR(f'Error adding category: {name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Category "{name}" already exists'))
