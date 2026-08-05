"""
Import fees straight from Paystack's Transaction List API.

`backfill_paystack_fees` replays payloads we already stored, so it can only
know about payments our webhooks actually caught. This command instead reads
Paystack's own record of every successful transaction on the integration —
including ones whose webhook never arrived, payments taken on the Paystack
dashboard, and anything predating fee capture entirely.

    python manage.py import_paystack_transactions --dry-run
    python manage.py import_paystack_transactions --since 2025-01-01
    python manage.py import_paystack_transactions --since 2025-01-01 --until 2025-12-31

Every fee here is Paystack's reported `fees`, never an estimate. Transactions
we can't match to an order still get recorded — an unattributed fee is real
money and belongs in the total. The `unlinked` count in the output tells you
how many those were.

Run this first, then `sync_paystack_fees` to fix up payout fees.
"""

from django.core.management.base import BaseCommand

from helpers.paystack_fees import import_fees_from_transactions_api


class Command(BaseCommand):
    help = "Import Paystack collection fees from the Transaction List API."

    def add_arguments(self, parser):
        parser.add_argument('--since', type=str, default=None,
                            help='Start date (YYYY-MM-DD).')
        parser.add_argument('--until', type=str, default=None,
                            help='End date (YYYY-MM-DD).')
        parser.add_argument('--per-page', type=int, default=100,
                            help='Transactions per API page (default 100).')
        parser.add_argument('--max-pages', type=int, default=50,
                            help='Maximum pages to walk (default 50).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be written without writing.')

    def handle(self, *args, **options):
        stats = import_fees_from_transactions_api(
            start_date=options['since'],
            end_date=options['until'],
            per_page=options['per_page'],
            max_pages=options['max_pages'],
            dry_run=options['dry_run'],
        )

        prefix = '[dry run] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Scanned {stats['scanned']} Paystack transactions across "
            f"{stats['pages']} page(s) — {stats['recorded']} fees recorded, "
            f"{stats['unlinked']} could not be matched to an order."
        ))
        if stats['scanned'] == 0:
            self.stdout.write(self.style.WARNING(
                "Nothing scanned. Check PAYSTACK_SECRET_KEY, and that the key "
                "is live rather than test if you expect live transactions."
            ))
        elif stats['pages'] >= options['max_pages']:
            self.stdout.write(self.style.WARNING(
                f"Hit the {options['max_pages']}-page limit — there may be more. "
                f"Re-run with a narrower --since/--until, or a higher --max-pages."
            ))
