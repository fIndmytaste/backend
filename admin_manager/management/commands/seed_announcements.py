from django.core.management.base import BaseCommand
from django.utils import timezone
from admin_manager.models import Announcement
from django.contrib.auth import get_user_model
import random

User = get_user_model()

TITLES = [
    "Welcome to FindMyTaste!",
    "New Feature: Track Your Orders",
    "Vendor Promo: 20% Off This Week",
    "Rider Safety Update",
    "Customer Appreciation Day",
    "System Maintenance Notice",
    "Refer a Friend, Get Rewards!",
    "Holiday Delivery Schedule",
    "Vendor Spotlight: Best of the Month",
    "Rider Bonus Program Announced"
]

MESSAGES = [
    "We're excited to have you on board. Explore the app and enjoy exclusive offers!",
    "You can now track your orders in real time from the app dashboard.",
    "Vendors are offering 20% off select items this week only. Don't miss out!",
    "Riders: Please review our updated safety guidelines before your next delivery.",
    "Thank you for being a valued customer. Enjoy special perks today!",
    "Scheduled maintenance will occur this weekend. Some features may be temporarily unavailable.",
    "Invite friends to FindMyTaste and earn rewards for every signup!",
    "Check our holiday delivery hours to plan your orders ahead.",
    "Meet our top-rated vendors and discover their best products.",
    "Riders: Earn bonuses for completing more deliveries this month!"
]

AUDIENCES = ["all", "customer", "vendor", "rider"]
PRIORITIES = ["low", "medium", "high", "critical"]

class Command(BaseCommand):
    help = "Seed 5-10 random announcements for testing."

    def handle(self, *args, **kwargs):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.ERROR("No superuser found. Please create one first."))
            return

        count = random.randint(5, 10)
        created = 0
        for i in range(count):
            title = random.choice(TITLES)
            message = random.choice(MESSAGES)
            target_audience = random.choice(AUDIENCES)
            priority = random.choice(PRIORITIES)
            start_date = timezone.now()
            end_date = start_date + timezone.timedelta(days=random.randint(2, 10))
            announcement = Announcement.objects.create(
                title=title,
                message=message,
                target_audience=target_audience,
                priority=priority,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
                is_published=True,
                send_push_notification=False,
                created_by=admin
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(f"Created announcement: {announcement.title} [{announcement.target_audience}]") )
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} announcements."))
