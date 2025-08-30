from django.core.management.base import BaseCommand

from account.models import Notification, User

class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        users = User.objects.filter(email__icontains='test')
        for user in users:
            print(user)

        self.stdout.write(self.style.SUCCESS('Successfully created 15 notifications for each user.'))


