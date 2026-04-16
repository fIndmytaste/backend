from django.core.management.base import BaseCommand
from account.models import FCMToken, Rider

class Command(BaseCommand):
    help = 'List all riders in the system.'

    def handle(self, *args, **options):
        riders = Rider.objects.all()
        if not riders:
            self.stdout.write(self.style.WARNING('No riders found.'))
            return
        for rider in riders:
            print("-----------------------------")
            # user fmc tokens
            tokens = FCMToken.objects.filter(user=rider.user, is_active=True)
            for token in tokens:
                self.stdout.write(f"Rider: {getattr(rider.user, 'full_name', 'N/A')} ({getattr(rider.user, 'email', 'N/A')}) - FCM Token: {token.token}")
            self.stdout.write(f"ID: {rider.id}, Name: {getattr(rider.user, 'full_name', 'N/A')}, Email: {getattr(rider.user, 'email', 'N/A')}")
