from django.core.management.base import BaseCommand
from account.models import User

class Command(BaseCommand):
    help = 'Set the referred_by field for a user using referral codes'

    def add_arguments(self, parser):
        parser.add_argument('--referee', required=True, help='Referral code or email of the user being referred')
        parser.add_argument('--referrer', required=True, help='Referral code or email of the referrer')

    def handle(self, *args, **options):
        referee_identifier = options['referee']
        referrer_identifier = options['referrer']

        # Try to get referee by referral code or email
        referee = User.objects.filter(referral_code=referee_identifier).first() or \
                  User.objects.filter(email=referee_identifier).first()
        # Try to get referrer by referral code or email
        referrer = User.objects.filter(referral_code=referrer_identifier).first() or \
                   User.objects.filter(email=referrer_identifier).first()

        if not referee:
            self.stdout.write(self.style.ERROR(f"Referee not found: {referee_identifier}"))
            return
        if not referrer:
            self.stdout.write(self.style.ERROR(f"Referrer not found: {referrer_identifier}"))
            return
        if referee == referrer:
            self.stdout.write(self.style.ERROR("A user cannot refer themselves."))
            return

        referee.referred_by = referrer
        referee.save()
        self.stdout.write(self.style.SUCCESS(f"{referee.email} is now referred by {referrer.email}"))
