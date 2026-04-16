from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from account.models import Rider
from product.models import Order

class Command(BaseCommand):
    help = 'Move 3 orders from one rider to another.'

    def add_arguments(self, parser):
        parser.add_argument('from_email', type=str, help='Email of the current rider (from)')
        parser.add_argument('to_email', type=str, help='Email of the target rider (to)')
        parser.add_argument('--count', type=int, default=3, help='Number of orders to move (default: 3)')

    def handle(self, *args, **options):
        from_email = options['from_email']
        to_email = options['to_email']
        count = max(1, min(options.get('count', 3), 10))  # Clamp between 1 and 10 for safety
        User = get_user_model()
        try:
            from_user = User.objects.get(email=from_email)
            to_user = User.objects.get(email=to_email)
            from_rider = Rider.objects.get(user=from_user)
            to_rider = Rider.objects.get(user=to_user)
        except User.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'User does not exist: {e}'))
            return
        except Rider.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Rider does not exist: {e}'))
            return

        # Get up to 'count' orders assigned to from_rider
        orders_to_move = Order.objects.filter(rider=to_rider, status__in=['pending', 'assigned_to_rider']).order_by('created_at')[:count]

        if not orders_to_move:
            self.stdout.write(self.style.WARNING(f'No orders found for rider {from_email} to move.'))
            return

        for order in orders_to_move:
            order.status = 'in_transit'
            # order.rider = to_rider
            # order.status = 'assigned_to_rider'  # Set to your appropriate status if needed
            order.save()
            self.stdout.write(self.style.SUCCESS(f'Order {order.id} moved from {from_email} to {to_email}.'))

        self.stdout.write(self.style.SUCCESS(f'{orders_to_move.count()} order(s) moved from {from_email} to {to_email}.'))
