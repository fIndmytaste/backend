from django.core.management.base import BaseCommand

from account.models import Notification, User, Vendor
from helpers.push_notification import NotificationHelper
from helpers.services.firebase_service import FirebaseNotificationService
from helpers.push_notification import send_login_notification
class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        user = User.objects.get(email='wale@gmail.com')
        result = FirebaseNotificationService.send_notification_to_user(
            user=user,
            title="Test",
            body="Test message"
        )

        if result["success"]:
            print(f"✅ Success! Sent to {result['success_count']} devices")
            if result.get('failure_count', 0) > 0:
                print(f"⚠️ Failed to send to {result['failure_count']} devices")
        else:
            print(f"❌ Failed: {result.get('error')}")
            print(user.id)
            # user.set_password('123456789')
            # user.save()
            # print(user)

        # wale@gmail.com
        # users = User.objects.filter(email__icontains='wale@gmail.com')
        # for user in users:
        #     result = send_login_notification(user)
        #     print(result)



        return 
        # TOKEN = 'evlUPPkcR-aKC-fa6P6LBy:APA91bEezVCzazjKJKYaM1b77w0MKr1HzBBoWMV01QAxfDgOCQO7LdOZhq39feuWAyFZuPLA5HbIVLOK9AGxL4pxxRAHiy0Q4JIQYtcDWnKJ_mc0s6T6M8s'
        TOKEN = 'dAn5M6QFpkmVmEGufomDm4:APA91bHZ2_kYRcVsK0czSDfxJylJlVKZG49JKlg_O30A6DT1mChSHFVhXFQ3t2uoj7FHPlIKOLYpFFV9Mv_SOhYstEIvP-0nyhZnUbszwhxF-PsJNz9mFZM'
        # TOKEN ="fNtLI7MR2UW7rc1u_STojz:APA91bEilnjKTVdm07mi9ZzY1TVHVg4pu87iJOKsFYBnIqTTKcsfxqdmto_squlpGWTlINbSvLFKTYPZnynqHMUC8C4N7tYHAkIz7LDf9ZDrK4ibjoA1Dfc"
        # TOKEN = "fNtLI7MR2UW7rc1u_STojz:APA91bEilnjKTVdm07mi9ZzY1TVHVg4pu87iJOKsFYBnIqTTKcsfxqdmto_squlpGWTlINbSvLFKTYPZnynqHMUC8C4N7tYHAkIz7LDf9ZDrK4ibjoA1Dfc"
        response = FirebaseNotificationService().send_notification_to_token(
            token=TOKEN,
            title="Testing vendor 2",
            body='olakay'
        )

        print(response)

        self.stdout.write(self.style.SUCCESS('Successfully created 15 notifications for each user.'))


