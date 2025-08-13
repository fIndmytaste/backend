import random
from django.core.management.base import BaseCommand

from account.models import Rider, User
from product.models import Order


class Command(BaseCommand):
    help = "Assign available riders to unassigned orders"

    def handle(self, *args, **options):
        user = User.objects.get(email="maria1@gmail.com")
        print(user.id)

        return 

        email = 'augustinevickky+11@gmail.com'
        rider = Rider.objects.get(user__email=email)
        print(rider.user.email)

        # return
        # Get all unassigned orders
        unassigned_orders = Order.objects.filter(rider__isnull=True, status='pending')

        if not unassigned_orders.exists():
            self.stdout.write(self.style.WARNING("🚫 No unassigned orders found."))
            return

        # Get all online and verified riders
        available_riders = list(Rider.objects.all())

        if not available_riders:
            self.stdout.write(self.style.WARNING("🚫 No available riders found."))
            return

        assigned_count = 0

        for order in unassigned_orders:
            rider = rider
            # rider = random.choice(available_riders)
            order.rider = rider
            order.status = 'confirmed'  # You can change this if needed
            order.save()
            assigned_count += 1
            self.stdout.write(f"✅ Assigned order {order.id} to rider {rider.user.email}")

        self.stdout.write(self.style.SUCCESS(f"🎉 Successfully assigned {assigned_count} orders."))
