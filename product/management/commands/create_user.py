from django.core.management.base import BaseCommand

from account.models import User, Vendor
from product.models import Product

import firebase_admin
from firebase_admin import credentials, messaging,exceptions
import traceback




class Command(BaseCommand):
    help = 'Creates predefined system categories in the database'

    def handle(self, *args, **kwargs):
        


        # 1. Initialize Firebase Admin SDK
        cred = credentials.Certificate("findmytaste-firebase-adminsdk.json")
        print(cred)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        fcm_token ="eUTHNALSeUlmhK8SJJJh9o:APA91bHpPtQmztk1HbPpbZajQmBPzVnbwYB3lJZUwLLRu6dqz-_roToKs5Zgi5CtLWra3S49PTqnx0YD11Pw5WI9sLrr4a0NjdMi1mMvHd6gitRxsU7cmhc"

        # 2. Function to send push notification
        def send_notification(device_token: str, title: str, body: str):
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=device_token
            )

            try:
                response = messaging.send(message)
                print("✅ Successfully sent message:", response)
            except exceptions.FirebaseError as e:
                print("❌ FirebaseError:", e)
                print("🔥 Error code:", e.code)
                print("📜 Error details:", e)
                # traceback.print_exc()
            except Exception as e:
                print("❌ Unexpected error:", str(e))
                traceback.print_exc()

        # Example usage
        send_notification(
                fcm_token,
                "Order Update",
                "Your order has been shipped 🚚"
            )
        # users = User.objects.filter(email__icontains="maria1@gmail.com")
        # for user in users:
        #     print(user.email)
        #     user.set_password('123456789')
        #     user.save()


        # product = Product.objects.get(id='4176ab13-e727-4cd4-a373-965efeff3261')
        # print(product)
        return
        # List of predefined categories to add
        user = User.objects.get(email="admin@findmytaste.com.ng")
        user.set_password("olakay")
        user.save()
