from django.core.management.base import BaseCommand
from account.models import Vendor
from django.utils import timezone

class Command(BaseCommand):
    help = 'Update a vendor\'s open_time, close_time, open_day, and close_day.'

    def add_arguments(self, parser):
        parser.add_argument('--vendor_id', type=str, required=True, help='Vendor ID (UUID)')
        parser.add_argument('--open_time', type=str, required=True, help='Opening time (HH:MM:SS)')
        parser.add_argument('--close_time', type=str, required=True, help='Closing time (HH:MM:SS)')
        parser.add_argument('--open_day', type=str, required=True, help='Opening day (e.g., Monday)')
        parser.add_argument('--close_day', type=str, required=True, help='Closing day (e.g., Saturday)')

    def handle(self, *args, **options):
        vendor_id = options['vendor_id']
        open_time = options['open_time']
        close_time = options['close_time']
        open_day = options['open_day']
        close_day = options['close_day']

        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'No vendor found with id {vendor_id}'))
            return

        vendor.open_time = open_time
        vendor.close_time = close_time
        vendor.open_day = open_day
        vendor.close_day = close_day
        vendor.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully updated vendor {vendor_id} opening/closing times and days.'))
