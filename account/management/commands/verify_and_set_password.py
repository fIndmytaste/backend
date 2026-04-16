from django.core.management.base import BaseCommand
from account.models import User

class Command(BaseCommand):
    help = 'Verify an account and set a new password for the user.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Email of the user to verify')
        parser.add_argument('--password', required=True, help='New password to set for the user')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with email {email} does not exist."))
            return

        user.is_verified = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"User {email} verified and password updated."))
