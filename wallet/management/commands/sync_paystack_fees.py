"""
Reconcile the fee ledger against Paystack's own balance ledger.

Charge webhooks report their fee, so collections are exact from the start.
Transfers usually don't — their fee rows begin life as estimates from the
published schedule. Paystack's balance ledger is the one endpoint that reports
the fee on every movement, so this command walks it and replaces estimates
with actuals.

    python manage.py sync_paystack_fees
    python manage.py sync_paystack_fees --since 2025-06-01 --until 2025-06-30

Safe to run repeatedly, and a good fit for a nightly cron.
"""

from django.core.management.base import BaseCommand

from helpers.paystack_fees import sync_payout_fees_from_ledger


class Command(BaseCommand):
    help = "Replace estimated Paystack fees with actuals from the balance ledger."

    def add_arguments(self, parser):
        parser.add_argument('--since', type=str, default=None,
                            help='Ledger start date (YYYY-MM-DD).')
        parser.add_argument('--until', type=str, default=None,
                            help='Ledger end date (YYYY-MM-DD).')
        parser.add_argument('--max-pages', type=int, default=20,
                            help='Ledger pages to walk (100 entries each).')

    def handle(self, *args, **options):
        stats = sync_payout_fees_from_ledger(
            start_date=options['since'],
            end_date=options['until'],
            max_pages=options['max_pages'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Scanned {stats['scanned']} ledger entries — "
            f"{stats['updated']} fees corrected, {stats['created']} rows added."
        ))
        if stats['scanned'] == 0:
            self.stdout.write(self.style.WARNING(
                "Nothing scanned. Check PAYSTACK_SECRET_KEY and that the "
                "account has ledger entries in the requested window."
            ))
