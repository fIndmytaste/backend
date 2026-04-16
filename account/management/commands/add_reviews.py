from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from account.models import Rider, RiderRating
from faker import Faker

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Add a review for a rider from all users on the platform with random comments'

    def handle(self, *args, **options):
        try:
            rider_user_id = str(input("Enter Rider's User ID: "))
        except ValueError:
            raise CommandError("Invalid input. Please enter a valid Rider User ID (integer).")

        try:
            rider = Rider.objects.get(user__email=rider_user_id)
        except Rider.DoesNotExist:
            raise CommandError(f'Rider with user_id {rider_user_id} does not exist.')

        users = User.objects.exclude(id=rider.user_id)  # exclude the rider themselves

        for user in users:
            rating = fake.pyfloat(min_value=1, max_value=5, right_digits=1)
            comment = fake.sentence(nb_words=10)

            rating_obj, created = RiderRating.objects.update_or_create(
                rider=rider,
                user=user,
                defaults={'rating': rating, 'comment': comment}
            )

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"Added rating {rating} by user {user.id} with comment: \"{comment}\""
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Updated rating by user {user.id} with rating {rating} and comment: \"{comment}\""
                ))

        self.stdout.write(self.style.SUCCESS(f"✅ All users have reviewed rider with user_id {rider_user_id}."))
