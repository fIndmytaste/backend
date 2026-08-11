"""Reconcile successful Paystack transfers with local withdrawal records."""

from django.core.management.base import BaseCommand

from helpers.paystack_fees import import_payouts_from_transfers_api


class Command(BaseCommand):
    help = "Import successful Paystack transfers and complete matching withdrawals."

    def add_arguments(self, parser):
        parser.add_argument('--since', type=str, default=None,
                            help='Start date (YYYY-MM-DD).')
        parser.add_argument('--until', type=str, default=None,
                            help='End date (YYYY-MM-DD).')
        parser.add_argument('--per-page', type=int, default=100)
        parser.add_argument('--max-pages', type=int, default=50)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        stats = import_payouts_from_transfers_api(
            start_date=options['since'],
            end_date=options['until'],
            per_page=options['per_page'],
            max_pages=options['max_pages'],
            dry_run=options['dry_run'],
        )
        prefix = '[dry run] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Scanned {stats['scanned']} transfers across "
            f"{stats['pages']} page(s): {stats['recorded']} successful payouts "
            f"recorded, {stats['completed_withdrawals']} local withdrawals "
            f"completed, {stats['unlinked']} unlinked."
        ))
