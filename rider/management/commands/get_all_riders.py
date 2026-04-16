from django.core.management.base import BaseCommand

from account.models import Rider

class Command(BaseCommand):
    help = 'Get all riders and print their details'

    def handle(self, *args, **options):
        riders = Rider.objects.all()
        if not riders:
            self.stdout.write(self.style.WARNING('No riders found.'))
            return
        for rider in riders:
            # print("-----------------------------")
            # print(f"ID: {rider.user.email if rider.user else 'N/A'}")
            # print(f"Name: {getattr(rider, 'name', 'N/A')}")
            if rider.user.email == 'augustinevickky+11@gmail.com':
                print(f"Email: augustinevickky+11@gmail.com  Latitude {rider.current_latitude}, Longitude {rider.current_longitude}, Updated At {rider.location_updated_at.time().strftime('%H:%M:%S')}")

            if rider.user.email == 'mexwes@gmail.com':
                print(f"Email: mexwes@gmail.com  Latitude {rider.current_latitude}, Longitude {rider.current_longitude}, Updated At {rider.location_updated_at.time().strftime('%H:%M:%S')}")