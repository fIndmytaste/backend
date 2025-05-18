from django.core.management.base import BaseCommand

from account.models import User

class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        # List of predefined categories to add
        user = User.objects.get(email="admin@findmytaste.com.ng")
        user.set_password("olakay")
        user.save()
