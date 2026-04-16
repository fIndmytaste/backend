from django.core.management.base import BaseCommand
from account.models import User

class Command(BaseCommand):
    help = 'List all users and their referral codes'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            self.stdout.write(f"{user.email} - Referral Code: {user.referral_code}")
