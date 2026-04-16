from django.core.management.base import BaseCommand
from product.models import Order

class Command(BaseCommand):
    help = 'Get an order by its track_id'

    def add_arguments(self, parser):
        parser.add_argument('track_id', type=str, help='The track_id of the order to retrieve')

    def handle(self, *args, **options):
        track_id = options['track_id']
        try:
            order = Order.objects.get(track_id=track_id)
            self.stdout.write(self.style.SUCCESS(f"Order found: {order.id} (track_id: {order.track_id}) : USER: {order.user.email}, Vendor: {order.vendor.name}, Status: {order.status}"))
            # self.stdout.write(str(order.__dict__))
        except Order.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Order with track_id {track_id} does not exist.'))
