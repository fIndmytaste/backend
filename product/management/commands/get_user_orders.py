from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from product.models import Order

class Command(BaseCommand):
    help = 'List all orders for a given user (by email or user ID).'

    def add_arguments(self, parser):
        parser.add_argument('identifier', type=str, help='User email or user ID')

    def handle(self, *args, **options):
        identifier = options['identifier']
        User = get_user_model()
        try:
            user = User.objects.filter(email=identifier).first()
            if not user:
                user = User.objects.filter(id=identifier).first()
            if not user:
                raise CommandError('User not found with the given email or ID.')

            orders = Order.objects.filter(user=user)
            if not orders:
                self.stdout.write(self.style.WARNING('No orders found for this user.'))
                return

            self.stdout.write(self.style.SUCCESS(f'Orders for {user.email} (ID: {user.id}):'))
            for order in orders:
                self.stdout.write(f'- Order ID: {order.id}, Status: {order.status}, Payment Status: {order.payment_status},  Created: {order.created_at}')
        except Exception as e:
            raise CommandError(f'Error: {e}')
