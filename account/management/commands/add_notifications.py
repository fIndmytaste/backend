from django.core.management.base import BaseCommand

from account.models import Notification, User

class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        for user in users:
            notifications = [
                Notification(
                    user=user,
                    title=f"Notification {i+1}",
                    content=f"This is notification number {i+1} for {user.first_name}"
                )
                for i in range(15)
            ]
            Notification.objects.bulk_create(notifications)

        self.stdout.write(self.style.SUCCESS('Successfully created 15 notifications for each user.'))


