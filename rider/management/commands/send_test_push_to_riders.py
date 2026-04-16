from django.core.management.base import BaseCommand
from account.models import Rider
from helpers.push_notification import NotificationHelper

class Command(BaseCommand):
    help = 'Send a test push notification to all riders.'

    def handle(self, *args, **options):
        riders = Rider.objects.select_related('user').all()
        if not riders:
            self.stdout.write(self.style.WARNING('No riders found.'))
            return
        users = [rider.user for rider in riders if rider.user]
        notification_helper = NotificationHelper()
        title = 'Test Notification'
        body = 'This is a test push notification to all riders.'
        for user in users:
            print("=================================")
            # print(f'Sending test notification to {user.email}...')
            notification_helper.send_to_user_async(
                user=user,
                title=title,
                body=body,
                data={"event": "test_notification"}
            )
        # self.stdout.write(f'Sending test notification to {len(users)} riders...')
        # notification_helper.send_to_multiple_users_async(users, title, body)
        # self.stdout.write(self.style.SUCCESS('Test push notification sent to all riders.'))
