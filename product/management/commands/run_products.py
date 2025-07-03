import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from account.models import Vendor
from product.models import Order, Product

User = get_user_model()


class Command(BaseCommand):
    help = "Seed 20 orders for the first user"

    def handle(self, *args, **kwargs):


        products = Product.objects.exclude(parent=None)
        
        
        for product in products:
            print(product.parent)
            print(product.parent.id)

        


