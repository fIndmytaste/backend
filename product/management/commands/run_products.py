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

        id = '984de313-80ec-43c1-bf31-280d304a9bab'

        vendor_id = '0ef634c1-ce5a-4819-8f8b-c443403ffe27'
        products = Product.objects.filter(vendor__id=vendor_id)
        
        # print(product.vendor.id)
        for product in products:
            if not product.parent:
                print(product.id)
            else:
                print("===========")
                print(product.parent, product.parent.id , product.id)
            # print(product.parent.id)

        


