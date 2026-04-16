from django.core.management.base import BaseCommand
from account.models import Vendor
from product.models import Order


class Command(BaseCommand):
    help = 'Delete all orders from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all orders',
        )

    def handle(self, *args, **options):

        in_progress_status = [
            # 'pending',
            'confirmed', 
            'preparing', 
            'looking_for_rider',
            'rider_assigned',
            'picked_up',
            'in_transit',
            'near_delivery'
        ]
        vendor = Vendor.objects.get(id='2b555c76-5c95-46c7-a924-4f1117d50044')
        queryset = Order.objects.filter(vendor=vendor, status__in=in_progress_status).order_by('-created_at')
        print(
            queryset.count()
        )
        for order in queryset:
            print(
                order.id,
                order.status
            )
        # if not options['confirm']:
        #     self.stdout.write(
        #         self.style.WARNING(
        #             'This command will delete ALL orders from the database.\n'
        #             'To proceed, run the command with the --confirm flag:\n'
        #             'python manage.py delete_all_orders --confirm'
        #         )
        #     )
        #     return

        # order_count = Order.objects.count()
        
        # if order_count == 0:
        #     self.stdout.write(self.style.SUCCESS('No orders to delete.'))
        #     return

        # # Delete all orders
        # Order.objects.all().delete()
        
        # self.stdout.write(
        #     self.style.SUCCESS(
        #         f'Successfully deleted {order_count} order(s) from the database.'
        #     )
        # )
