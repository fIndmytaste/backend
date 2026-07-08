from django.core.management.base import BaseCommand

from rider.tasks import process_weekly_rider_payouts


class Command(BaseCommand):
    help = (
        "Run the weekly rider payout immediately (same logic as the "
        "celery beat schedule). Pays every active independent rider their "
        "accumulated wallet balance to their bank account."
    )

    def handle(self, *args, **options):
        summary = process_weekly_rider_payouts()
        self.stdout.write(self.style.SUCCESS(f"Weekly rider payout run complete: {summary}"))
