"""
Rebuild the Paystack fee ledger from history.

Fee capture only starts recording from the moment it ships, which would leave
every past order looking fee-free and make period-over-period revenue
comparisons meaningless. But the raw Paystack payloads are already on disk:
`WalletTransaction.response_data` holds the full verify/webhook body for every
completed payment, and those bodies carry Paystack's `fees`.

This command replays them.

    python manage.py backfill_paystack_fees                 # from stored payloads
    python manage.py backfill_paystack_fees --estimate-missing
    python manage.py backfill_paystack_fees --since 2025-01-01 --dry-run

`--estimate-missing` additionally covers paid orders that have no stored
payload at all (older rows, wallet-paid orders re-keyed later) by applying the
published fee schedule. Those rows are flagged `is_estimated=True` so the
dashboard reports them separately — run `sync_paystack_fees` afterwards to
replace them with Paystack's actual numbers where the ledger reaches.
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from helpers.paystack_fees import (
    estimate_collection_fee,
    read_collection,
    read_payout,
    record_collection_fee,
    record_payout_fee,
)
from product.models import Order
from wallet.models import PaystackFeeRecord, WalletTransaction


COLLECTION_TYPES = ('purchase', 'deposit')


class Command(BaseCommand):
    help = "Backfill Paystack fee records from stored transaction payloads."

    def add_arguments(self, parser):
        parser.add_argument(
            '--since', type=str, default=None,
            help='Only process transactions created on/after this date (YYYY-MM-DD).')
        parser.add_argument(
            '--estimate-missing', action='store_true',
            help='Also create estimated fee rows for paid orders with no stored payload.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be written without touching the database.')

    def handle(self, *args, **options):
        since = None
        if options['since']:
            try:
                since = timezone.make_aware(
                    datetime.strptime(options['since'], '%Y-%m-%d'),
                    timezone.get_current_timezone(),
                )
            except ValueError:
                self.stderr.write(self.style.ERROR('--since must be YYYY-MM-DD'))
                return

        dry_run = options['dry_run']
        stats = {'collections': 0, 'payouts': 0, 'estimated_orders': 0, 'skipped': 0}

        # ── 1. Replay stored Paystack payloads ─────────────────────────────
        transactions = WalletTransaction.objects.filter(
            response_data__isnull=False, status='completed',
        ).select_related('order', 'user', 'wallet')
        if since:
            transactions = transactions.filter(created_at__gte=since)

        for txn in transactions.iterator(chunk_size=200):
            payload = txn.response_data
            if not isinstance(payload, dict):
                stats['skipped'] += 1
                continue

            if txn.transaction_type in COLLECTION_TYPES:
                parsed = read_collection(payload)
                if not parsed or not parsed.get('reference'):
                    stats['skipped'] += 1
                    continue
                if not dry_run:
                    record_collection_fee(
                        payload, wallet_transaction=txn, source='backfill')
                stats['collections'] += 1

            elif txn.transaction_type == 'withdrawal':
                parsed = read_payout(payload)
                if not parsed:
                    stats['skipped'] += 1
                    continue
                # Payout payloads are keyed on our own transaction id, which is
                # what the transfer webhook uses too — keep them aligned.
                payload = dict(payload)
                data = payload.get('data')
                if isinstance(data, dict) and not data.get('reference'):
                    data = dict(data)
                    data['reference'] = str(txn.id)
                    payload['data'] = data
                elif not isinstance(data, dict) and not payload.get('reference'):
                    payload['reference'] = str(txn.id)
                if not dry_run:
                    record_payout_fee(
                        payload, wallet_transaction=txn, source='backfill')
                stats['payouts'] += 1

        # ── 2. Paid orders we have no payload for ──────────────────────────
        if options['estimate_missing']:
            covered = set(
                PaystackFeeRecord.objects
                .filter(direction='collection', order__isnull=False)
                .values_list('order_id', flat=True)
            )
            orders = Order.objects.filter(payment_status='paid', payment_method='link')
            if since:
                orders = orders.filter(created_at__gte=since)

            for order in orders.exclude(id__in=covered).iterator(chunk_size=200):
                gross = order.total_amount or 0
                if gross <= 0:
                    continue
                fee = estimate_collection_fee(gross, 'card')
                if not dry_run:
                    PaystackFeeRecord.objects.update_or_create(
                        direction='collection',
                        reference=f'order:{order.id}',
                        defaults={
                            'order': order,
                            'user': order.user,
                            'channel': 'card',
                            'gross_amount': gross,
                            'fee_amount': fee,
                            'net_amount': gross - fee,
                            'is_estimated': True,
                            'source': 'estimate',
                            'paid_at': order.created_at,
                        },
                    )
                stats['estimated_orders'] += 1

        prefix = '[dry run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Backfilled {stats['collections']} collections, "
            f"{stats['payouts']} payouts, "
            f"{stats['estimated_orders']} estimated order fees "
            f"({stats['skipped']} payloads skipped)."
        ))
        if not dry_run and (stats['payouts'] or stats['estimated_orders']):
            self.stdout.write(
                "Next: run `python manage.py sync_paystack_fees` to replace "
                "estimated fees with Paystack's actual ledger numbers."
            )
