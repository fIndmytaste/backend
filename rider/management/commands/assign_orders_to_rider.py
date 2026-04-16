from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rider.models import Rider
from api.models import Order

class Command(BaseCommand):
    help = 'Assign 2-3 available orders to a rider by email.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email of the rider user')
        parser.add_argument('--count', type=int, default=2, help='Number of orders to assign (default: 2, max: 3)')

    def handle(self, *args, **options):
        email = options['email']
        count = min(max(options.get('count', 2), 2), 3)  # Clamp between 2 and 3
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
            rider = Rider.objects.get(user=user)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with email {email} does not exist.'))
            return
        except Rider.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Rider for user {email} does not exist.'))
            return

        # Get available orders (not assigned to any rider)
        available_orders = Order.objects.filter(rider=None, status__in=['looking_for_rider', 'awaiting_rider']).order_by('created_at')[:count]
        if not available_orders:
            self.stdout.write(self.style.WARNING('No available orders to assign.'))
            return

        for order in available_orders:
            order.rider = rider
            order.status = 'assigned_to_rider'  # Set to your appropriate status if needed
            order.save()
            self.stdout.write(self.style.SUCCESS(f'Order {order.id} assigned to {email}.'))

        self.stdout.write(self.style.SUCCESS(f'{available_orders.count()} order(s) assigned to {email}.'))
