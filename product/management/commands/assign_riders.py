import uuid
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from account.models import Vendor
from product.models import Order, OrderItem, Product

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate 20 confirmed orders for a specific vendor.'

    def handle(self, *args, **kwargs):

        orders =  Order.objects.filter(id='f5061579-e5e2-443e-9738-5f6a82dbb5c2')
        # orders =  Order.objects.filter(rider=None, status__in=['pending','confirmed'])
        
        for order in orders:
            print(order)


        return




        vendor_id = '2b555c76-5c95-46c7-a924-4f1117d50044'

        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            self.stderr.write(f"Vendor with ID {vendor_id} does not exist.")
            return

        # Use any active user or create one dummy
        user = User.objects.first()
        if not user:
            self.stderr.write("No user found in the system.")
            return

        # Get products by the vendor
        products = Product.objects.filter(vendor=vendor)

        if not products.exists():
            self.stderr.write(f"No products found for vendor {vendor_id}")
            return

        for i in range(20):
            order = Order.objects.create(
                user=user,
                vendor=vendor,
                status='confirmed',
                payment_status='paid',
                total_amount=0,  # will update after adding items
                delivery_fee=random.randint(500, 1500),
                service_fee=random.randint(100, 300),
                country="Nigeria",
                state="Lagos",
                city="Lekki",
                address=f"Test Address {i + 1}",
                location_latitude=6.6940015,
                location_longitude=3.350708,
                new_estimated_pickup_time=timedelta(minutes=20),
                new_estimated_delivery_time=timedelta(minutes=40),
                payment_method='wallet',
            )

            # Randomly pick 1-3 products for this order
            selected_products = random.sample(list(products), min(3, len(products)))
            total = 0

            for product in selected_products:
                quantity = random.randint(1, 3)
                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                )
                total += product.price * quantity

            # Add fees to total
            total += order.delivery_fee + order.service_fee
            order.total_amount = total
            order.save()

            self.stdout.write(f"✅ Created order {order.id} with total ₦{total}")

        self.stdout.write(self.style.SUCCESS("🎉 Successfully created 20 confirmed orders."))
