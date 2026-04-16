from django.core.management.base import BaseCommand
from account.models import User
from helpers.push_notification import NotificationHelper

class Command(BaseCommand):
    help = 'Send a test push notification to a specific user by email.'

    def handle(self, *args, **options):
        email = 'kabby123@gmail.com'
        # email = 'augustinevickky+11@gmail.com'
        users = User.objects.filter(email=email)
        if not users.exists():
            self.stdout.write(self.style.ERROR(f'User with email {email} does not exist.'))
            return
 

        notification_helper = NotificationHelper()
        title = 'Test Notification'
        body = 'This is a test push notification.'
        res = notification_helper.send_to_users_with_executor(users, title, body)
        self.stdout.write(self.style.SUCCESS(f'Push notification send result: {res}'))
        self.stdout.write(self.style.SUCCESS(f'Test push notification sent to {email}'))
