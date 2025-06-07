import random
from django.core.management.base import BaseCommand
from faker import Faker

from account.models import Rider, RiderRating, User

fake = Faker()

class Command(BaseCommand):
    help = 'Add a review to each existing rider'

    def handle(self, *args, **options):
        riders = Rider.objects.all()

        if not riders.exists():
            self.stdout.write(self.style.WARNING("🚫 No riders found."))
            return

        for index, rider in enumerate(riders, start=1):
            # Create or reuse reviewer
            reviewer_email = f"reviewer{index}@example.com"
            reviewer, created = User.objects.get_or_create(
                email=reviewer_email,
                defaults={
                    "password": "password123",
                    "full_name": fake.name(),
                    "role": "buyer",
                    "is_active": True,
                }
            )

            # Skip if already rated
            if RiderRating.objects.filter(rider=rider, user=reviewer).exists():
                self.stdout.write(self.style.WARNING(
                    f"⚠️ {reviewer.email} already rated {rider.user.email}"
                ))
                continue

            rating_value = round(random.uniform(3.0, 5.0), 1)
            comment = fake.sentence(nb_words=10)

            RiderRating.objects.create(
                rider=rider,
                user=reviewer,
                rating=rating_value,
                comment=comment
            )

            self.stdout.write(self.style.SUCCESS(
                f"✅ Added {rating_value}⭐ review by {reviewer.email} to {rider.user.email}"
            ))

        self.stdout.write(self.style.SUCCESS("🎉 Done adding reviews to riders."))
