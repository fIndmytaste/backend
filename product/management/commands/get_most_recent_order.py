from django.core.management.base import BaseCommand
from product.models import Order

class Command(BaseCommand):
    help = 'Get the most recent order'

    def handle(self, *args, **options):
        most_recent_order = Order.objects.order_by('-created_at').first()
        if most_recent_order:
            self.stdout.write(self.style.SUCCESS(
                f"Most recent order: {most_recent_order.id} (created at {most_recent_order.created_at}) : Vendor earnings: {most_recent_order.vendor_amount}, Platform earnings: {most_recent_order.platform_amount}"
            ))
            # Optionally print more details
            # self.stdout.write(str(most_recent_order.__dict__))
        else:
            self.stdout.write(self.style.WARNING('No orders found.'))
