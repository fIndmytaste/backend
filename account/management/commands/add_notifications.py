from django.core.management.base import BaseCommand

from account.models import Notification, User
from helpers.push_notification import NotificationHelper
from helpers.services.firebase_service import FirebaseNotificationService

class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        # users = User.objects.filter(email__icontains='test')
        # for user in users:
        #     print(user)

        TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU1MTA3NDg0LCJpYXQiOjE3NTQ5Mjc4MzcsImp0aSI6IjI1YjIyMTIyOTc5YTRkYzNiYjg0OGYxZWZlY2UxM2ViIiwidXNlcl9pZCI6IjA1ODk4YTg0LTM5MTYtNGJiNC1hZmVkLWU4NWViYTI4ZDExYiJ9.YjzSeATZUa3xmHBpQIFqhpwbjlVmaaHHDbx3nzKUppQ'
        response = FirebaseNotificationService().send_notification_to_token(
            token=TOKEN,
            title="Testing",
            body='olakay'
        )

        print(response)

        self.stdout.write(self.style.SUCCESS('Successfully created 15 notifications for each user.'))


