from django.core.management.base import BaseCommand
from account.models import Guarantor

class Command(BaseCommand):
    help = 'List all guarantors and their rider user emails.'

    def handle(self, *args, **options):
        self.stdout.write('Guarantor Name | Phone | Relationship | Rider Email')
        for guarantor in Guarantor.objects.select_related('rider__user').all():
            rider_email = guarantor.rider.user.email if guarantor.rider and guarantor.rider.user else 'N/A'
            self.stdout.write(f'{guarantor.name} | {guarantor.phone_number} | {guarantor.relationship or "-"} | {rider_email}')
