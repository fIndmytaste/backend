from django.core.management.base import BaseCommand
from account.models import FCMToken

class Command(BaseCommand):
    help = 'Get all FCM tokens and print their details.'

    def handle(self, *args, **options):
        tokens = FCMToken.objects.select_related('user').all()
        if not tokens:
            self.stdout.write(self.style.WARNING('No FCM tokens found.'))
            return
        self.stdout.write(f"Total FCM tokens: {tokens.count()}")
        for token in tokens:
            self.stdout.write(f"User: {token.user.email if token.user else 'N/A'} | Token: {token.token} | Platform: {token.platform} | Active: {token.is_active}")
