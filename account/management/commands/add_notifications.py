from django.core.management.base import BaseCommand

from account.models import Notification, User

class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        # List of predefined categories to add
        Notification
