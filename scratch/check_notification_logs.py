import os
import sys
import django

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'findmytaste.settings')
django.setup()

from account.models import PushNotificationLog

# Filter for specific user if provided
email = "olakaycoder1@gmail.com"
logs = PushNotificationLog.objects.filter(user__email=email).order_by('-created_at')[:10]

if not logs:
    print(f"No logs found for {email}")
    logs = PushNotificationLog.objects.all().order_by('-created_at')[:20]

for log in logs:
    print(f"User: {log.user.email}")
    print(f"Title: {log.title}")
    print(f"Body: {log.body}")
    print(f"Status: {log.status}")
    print(f"Created At: {log.created_at}")
    print(f"Firebase Message ID: {log.firebase_message_id}")
    print(f"Error Message: {log.error_message}")
    print(f"Data: {log.data}")
    print("-" * 20)
