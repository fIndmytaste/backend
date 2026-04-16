from django.core.management.base import BaseCommand, CommandError
from product.models import Order
from helpers.referral_logic import process_referral_reward

class Command(BaseCommand):
    help = 'Test process_referral_reward for a given order ID.'

    def add_arguments(self, parser):
        parser.add_argument('order_id', type=str, help='Order ID to test referral reward')

    def handle(self, *args, **options):
        order_id = options['order_id']
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise CommandError(f'Order with ID {order_id} not found.')
        try:
            process_referral_reward(order)
            self.stdout.write(self.style.SUCCESS(f'Referral reward processed for order {order_id}.'))
        except Exception as e:
            raise CommandError(f'Error processing referral reward: {e}')
