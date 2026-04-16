from django.utils import timezone
from django.core.management.base import BaseCommand
import random
from uuid import uuid4
from account.models import User, Vendor
from product.models import Order, OrderItem, Product  # Don't forget to import this


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # admin_user = User.objects.filter(is_admin=True).first()
        vendor = Vendor.objects.get(id='2b555c76-5c95-46c7-a924-4f1117d50044')

        print(vendor.id)
        print(vendor.user.email)

        # user = User.objects.get(email=vendor.user.email)
        # user.set_password('123456')
        # user.save()

        return

        products = Product.objects.filter(parent=None,vendor=vendor)

        if not products.exists():
            self.stdout.write(self.style.ERROR('Vendor has no products. Cannot create orders.'))
            return

        for i in range(5):
            product = random.choice(products)
            quantity = random.randint(1, 5)
            price = product.price

            order = Order.objects.create(
                user=admin_user,
                vendor=vendor,
                country='Nigeria',
                state='Lagos',
                city='Ikeja',
                address='123 Admin Street',
                location_latitude=6.5244,
                location_longitude=3.3792,
                status='confirmed',
                payment_status='paid',
            )

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price,
            )

            order.update_total_amount()  # Recalculates and saves total
            self.stdout.write(self.style.SUCCESS(f'Created order {order.track_id} with product "{product.name}" x{quantity}'))
