from django.core.management.base import BaseCommand
from product.promo_models import PromoCode

class Command(BaseCommand):
    help = 'List all promo codes.'

    def handle(self, *args, **options):
        promos = PromoCode.objects.all()
        if not promos:
            self.stdout.write(self.style.WARNING('No promo codes found.'))
            return
        self.stdout.write(self.style.SUCCESS('Promo Codes:'))
        for promo in promos:
            self.stdout.write(f"- {promo.code}: {promo.description} (Active: {promo.is_active})")
