from django.core.management.base import BaseCommand

from account.models import User
from product.models import Product

class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):

        product = Product.objects.get(id='4176ab13-e727-4cd4-a373-965efeff3261')
        print(product)
        return
        # List of predefined categories to add
        user = User.objects.get(email="admin@findmytaste.com.ng")
        user.set_password("olakay")
        user.save()
