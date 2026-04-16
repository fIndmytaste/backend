from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from product.models import Order

class Command(BaseCommand):
    help = 'Get the number of orders for a user and optionally clear them.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email')
        parser.add_argument('--clear', action='store_true', help='Delete all orders for the user')

    def handle(self, *args, **options):
        email = options['email']
        clear = options['clear']
        User = get_user_model()
        try:
            user = User.objects.filter(email=email).first()
            if not user:
                raise CommandError('User not found.')
            orders = Order.objects.filter(user=user)
            order_count = orders.count()
            self.stdout.write(self.style.SUCCESS(f'User {email} has {order_count} order(s).'))
            if clear:
                deleted, _ = orders.delete()
                self.stdout.write(self.style.WARNING(f'Deleted {deleted} order(s) for user {email}.'))
        except Exception as e:
            raise CommandError(f'Error: {e}')
