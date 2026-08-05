"""
Admin Analytics: Paystack fees & net platform revenue
=====================================================
Endpoints:
  GET  /admin-manager/analytics/paystack-fees/
       Full fee picture for a period: gross collected, what Paystack took,
       what settled, and platform revenue net of it — with breakdowns by
       direction and channel, a daily series, and the costliest movements.

  GET  /admin-manager/analytics/paystack-fees/transactions/
       Paginated line-by-line list of Paystack movements and their fees.

  POST /admin-manager/analytics/paystack-fees/sync/
       Reconcile against Paystack's balance ledger, replacing estimated fees
       (mostly payouts, whose webhooks don't report a fee) with actuals.

Fees are read from wallet.PaystackFeeRecord, which is written from Paystack's
own payloads at every point money moves. Rows flagged `is_estimated` came from
the published fee schedule because the payload carried no fee; the sync
endpoint above is what turns those into reported numbers.
"""

from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, timedelta

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from helpers.date_range import parse_date_range
from helpers.response.response_format import (
    bad_request_response,
    internal_server_error_response,
    paginate_success_response_with_serializer,
    success_response,
)
from product.models import Order
from wallet.models import PaystackFeeRecord
from admin_manager.serializers.paystack_fees import PaystackFeeRecordSerializer


PERIOD_DELTAS = {
    'day': timedelta(days=1),
    'week': timedelta(days=7),
    'month': timedelta(days=30),
    'year': timedelta(days=365),
}
PERIOD_ALIASES = {
    'daily': 'day', 'weekly': 'week', 'monthly': 'month', 'yearly': 'year',
}


def resolve_window(request):
    """
    Work out the reporting window from `start_date`/`end_date` (which win) or
    the rolling `period` / `time_range` dropdown. Returns (start, end, label);
    `end` is None for an open-ended rolling window.
    """
    custom_start, custom_end = parse_date_range(request)
    tz = timezone.get_current_timezone()

    if custom_start or custom_end:
        start = (
            timezone.make_aware(datetime.combine(custom_start, datetime.min.time()), tz)
            if custom_start else None
        )
        # Inclusive end day → exclusive upper bound at the following midnight.
        end = (
            timezone.make_aware(
                datetime.combine(custom_end + timedelta(days=1), datetime.min.time()), tz)
            if custom_end else None
        )
        return start, end, 'custom'

    raw = (
        request.GET.get('period')
        or request.GET.get('time_range')
        or 'week'
    ).lower()
    period = PERIOD_ALIASES.get(raw, raw)
    delta = PERIOD_DELTAS.get(period)
    if delta is None:
        period, delta = 'week', PERIOD_DELTAS['week']
    return timezone.now() - delta, None, period


def window_filter(start, end, field='paid_at'):
    bounds = {}
    if start:
        bounds[f'{field}__gte'] = start
    if end:
        bounds[f'{field}__lt'] = end
    return bounds


def _f(value):
    """Decimal/None → float, for JSON."""
    return float(value or 0)


class AdminPaystackFeeAnalyticsView(generics.GenericAPIView):
    """
    GET /admin-manager/analytics/paystack-fees/

    Query params:
      period      – day | week | month | year (default week)
      start_date  – YYYY-MM-DD (overrides period)
      end_date    – YYYY-MM-DD
      limit       – how many top-fee movements to return (default 10)
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Paystack fees & net platform revenue",
        operation_description=(
            "Everything Paystack charged the platform in a period — collection "
            "fees on money in, transfer fees on money out — alongside gross "
            "collections, net settlement, and platform revenue net of fees."
        ),
        manual_parameters=[
            openapi.Parameter('period', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=['day', 'week', 'month', 'year'],
                              description="Rolling window (default week)."),
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD — overrides period.'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD (inclusive).'),
            openapi.Parameter('limit', openapi.IN_QUERY, type=openapi.TYPE_INTEGER,
                              description='Top costliest movements to return (default 10).'),
        ],
        responses={200: 'Paystack fee analytics', 401: 'Unauthorized'},
    )
    def get(self, request):
        try:
            start, end, period = resolve_window(request)
            try:
                limit = max(1, min(int(request.GET.get('limit', 10)), 100))
            except (TypeError, ValueError):
                limit = 10

            records = PaystackFeeRecord.objects.filter(
                **window_filter(start, end))

            # ── Headline totals ────────────────────────────────────────────
            totals = records.aggregate(
                collection_fees=Sum('fee_amount', filter=Q(direction='collection')),
                payout_fees=Sum('fee_amount', filter=Q(direction='payout')),
                gross_collected=Sum('gross_amount', filter=Q(direction='collection')),
                net_settled=Sum('net_amount', filter=Q(direction='collection')),
                gross_paid_out=Sum('gross_amount', filter=Q(direction='payout')),
                total_debited=Sum('net_amount', filter=Q(direction='payout')),
                collection_count=Count('id', filter=Q(direction='collection')),
                payout_count=Count('id', filter=Q(direction='payout')),
                estimated_fees=Sum('fee_amount', filter=Q(is_estimated=True)),
                estimated_count=Count('id', filter=Q(is_estimated=True)),
            )

            collection_fees = Decimal(str(totals['collection_fees'] or 0))
            payout_fees = Decimal(str(totals['payout_fees'] or 0))
            total_fees = collection_fees + payout_fees
            gross_collected = Decimal(str(totals['gross_collected'] or 0))
            estimated_fees = Decimal(str(totals['estimated_fees'] or 0))

            # Effective take rate: what share of everything customers paid ends
            # up with Paystack. The single number to watch month over month.
            effective_rate = (
                (collection_fees / gross_collected * 100)
                if gross_collected else Decimal('0')
            )

            # ── Platform revenue over the same window, so "net" is derivable
            #    here without a second call to the overview endpoint. ────────
            paid_orders = Order.objects.filter(
                payment_status='paid', **window_filter(start, end, 'created_at'))
            marketplace_filter = (
                Q(vendor__is_marketplace=True) | Q(vendor__marketplace__isnull=False)
            )
            vendor_service_charges = paid_orders.aggregate(
                total=Sum('platform_amount'))['total'] or 0
            delivery_service_fees = paid_orders.exclude(marketplace_filter).distinct().aggregate(
                total=Sum('service_fee'))['total'] or 0
            recorded_marketplace_delivery = paid_orders.filter(
                platform_marketplace_delivery_amount__isnull=False,
            ).aggregate(total=Sum('platform_marketplace_delivery_amount'))['total'] or 0
            legacy_marketplace_delivery = (
                paid_orders
                .filter(platform_marketplace_delivery_amount__isnull=True)
                .filter(marketplace_filter)
                .distinct()
                .aggregate(total=Sum('delivery_fee'))['total'] or 0
            )
            platform_earnings = (
                Decimal(str(vendor_service_charges))
                + Decimal(str(delivery_service_fees))
                + Decimal(str(recorded_marketplace_delivery))
                + Decimal(str(legacy_marketplace_delivery))
            )
            net_platform_revenue = platform_earnings - total_fees
            fee_share_of_earnings = (
                (total_fees / platform_earnings * 100)
                if platform_earnings else Decimal('0')
            )

            # ── By channel: which payment method costs us most ─────────────
            by_channel = [
                {
                    'channel': row['channel'] or 'unknown',
                    'movements': row['movements'],
                    'gross_amount': _f(row['gross']),
                    'fee_amount': _f(row['fees']),
                    'effective_rate_percent': round(
                        (float(row['fees'] or 0) / float(row['gross']) * 100), 3
                    ) if row['gross'] else 0.0,
                }
                for row in records.values('channel').annotate(
                    movements=Count('id'),
                    gross=Sum('gross_amount'),
                    fees=Sum('fee_amount'),
                ).order_by('-fees')
            ]

            # ── Daily series for charting ──────────────────────────────────
            daily = [
                {
                    'date': row['day'].isoformat() if row['day'] else None,
                    'collection_fees': _f(row['collection_fees']),
                    'payout_fees': _f(row['payout_fees']),
                    'total_fees': _f(row['collection_fees']) + _f(row['payout_fees']),
                    'gross_collected': _f(row['gross_collected']),
                }
                for row in records.annotate(day=TruncDate('paid_at')).values('day').annotate(
                    collection_fees=Sum('fee_amount', filter=Q(direction='collection')),
                    payout_fees=Sum('fee_amount', filter=Q(direction='payout')),
                    gross_collected=Sum('gross_amount', filter=Q(direction='collection')),
                ).order_by('day')
            ]

            # ── Costliest individual movements ─────────────────────────────
            top_movements = [
                {
                    'id': str(record.id),
                    'direction': record.direction,
                    'reference': record.reference,
                    'channel': record.channel,
                    'gross_amount': _f(record.gross_amount),
                    'fee_amount': _f(record.fee_amount),
                    'net_amount': _f(record.net_amount),
                    'is_estimated': record.is_estimated,
                    'paid_at': record.paid_at.isoformat() if record.paid_at else None,
                    'order_id': str(record.order_id) if record.order_id else None,
                }
                for record in records.order_by('-fee_amount')[:limit]
            ]

            return success_response(data={
                'period': period,
                'window': {
                    'start': start.isoformat() if start else None,
                    'end': end.isoformat() if end else None,
                },
                'summary': {
                    # Money in
                    'gross_collected': _f(totals['gross_collected']),
                    'collection_fees': float(collection_fees),
                    'net_settled': _f(totals['net_settled']),
                    'collection_count': totals['collection_count'] or 0,
                    # Money out
                    'gross_paid_out': _f(totals['gross_paid_out']),
                    'payout_fees': float(payout_fees),
                    'total_debited_for_payouts': _f(totals['total_debited']),
                    'payout_count': totals['payout_count'] or 0,
                    # The bottom line
                    'total_paystack_fees': float(total_fees),
                    'platform_earnings': float(platform_earnings),
                    'net_platform_revenue': float(net_platform_revenue),
                    'effective_collection_rate_percent': round(float(effective_rate), 3),
                    'fees_as_percent_of_platform_earnings': round(
                        float(fee_share_of_earnings), 3),
                },
                'confidence': {
                    'reported_amount': float(total_fees - estimated_fees),
                    'estimated_amount': float(estimated_fees),
                    'estimated_movements': totals['estimated_count'] or 0,
                    'total_movements': (
                        (totals['collection_count'] or 0) + (totals['payout_count'] or 0)),
                    'note': (
                        'Estimated fees come from the published Paystack fee '
                        'schedule because the payload carried no fee — usually '
                        'payouts. POST to /analytics/paystack-fees/sync/ to '
                        'replace them with Paystack balance-ledger actuals.'
                    ),
                },
                'by_channel': by_channel,
                'daily': daily,
                'top_movements': top_movements,
            })

        except Exception as e:
            print(f"[AdminPaystackFeeAnalyticsView] Error: {e}")
            return internal_server_error_response()


class AdminPaystackFeeTransactionListView(generics.GenericAPIView):
    """
    GET /admin-manager/analytics/paystack-fees/transactions/

    Line-by-line Paystack movements with their fees. Filterable by direction,
    channel, and whether the fee is still an estimate.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaystackFeeRecordSerializer

    @swagger_auto_schema(
        operation_summary="Paystack fee ledger (paginated)",
        manual_parameters=[
            openapi.Parameter('period', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=['day', 'week', 'month', 'year']),
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('direction', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=['collection', 'payout', 'reversal']),
            openapi.Parameter('channel', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('estimated_only', openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN,
                              description='Only rows whose fee is still estimated.'),
        ],
        responses={200: PaystackFeeRecordSerializer(many=True), 401: 'Unauthorized'},
    )
    def get(self, request):
        start, end, _period = resolve_window(request)
        queryset = (
            PaystackFeeRecord.objects
            .filter(**window_filter(start, end))
            .select_related('order', 'user', 'wallet_transaction')
        )

        direction = (request.GET.get('direction') or '').strip()
        if direction:
            queryset = queryset.filter(direction=direction)

        channel = (request.GET.get('channel') or '').strip()
        if channel:
            queryset = queryset.filter(channel__iexact=channel)

        if str(request.GET.get('estimated_only', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(is_estimated=True)

        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            queryset.order_by('-paid_at'),
            page_size=int(request.GET.get('page_size', 20)),
        )


class AdminPaystackFeeSyncView(generics.GenericAPIView):
    """
    POST /admin-manager/analytics/paystack-fees/sync/

    Walk Paystack's balance ledger and replace estimated fees with the actual
    ones Paystack recorded. Safe to run repeatedly — it only corrects rows.

    Optional body: { "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD" }
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Reconcile fees against the Paystack balance ledger",
        operation_description=(
            "Fetches Paystack's balance ledger and overwrites estimated fees "
            "with reported ones. Creates rows for movements we never saw."
        ),
        responses={200: 'Sync result', 401: 'Unauthorized'},
    )
    def post(self, request):
        from helpers.paystack_fees import (
            import_fees_from_transactions_api,
            sync_payout_fees_from_ledger,
        )

        start_date = request.data.get('start_date') or None
        end_date = request.data.get('end_date') or None
        # 'ledger' fixes payout estimates; 'transactions' pulls collection fees
        # straight from Paystack (catching anything our webhooks missed).
        source = (request.data.get('source') or 'both').lower()
        if source not in ('ledger', 'transactions', 'both'):
            return bad_request_response(
                message="source must be one of: ledger, transactions, both.")

        result = {}
        try:
            if source in ('transactions', 'both'):
                result['transactions'] = import_fees_from_transactions_api(
                    start_date=start_date, end_date=end_date)
            if source in ('ledger', 'both'):
                result['ledger'] = sync_payout_fees_from_ledger(
                    start_date=start_date, end_date=end_date)
        except Exception as e:
            print(f"[AdminPaystackFeeSyncView] Error: {e}")
            return bad_request_response(message="Could not reach the Paystack API.")

        parts = []
        if 'transactions' in result:
            parts.append(
                f"{result['transactions']['recorded']} collection fees imported "
                f"from {result['transactions']['scanned']} transactions")
        if 'ledger' in result:
            parts.append(
                f"{result['ledger']['updated']} fees corrected and "
                f"{result['ledger']['created']} added from the balance ledger")

        return success_response(
            message="Reconciled with Paystack — " + "; ".join(parts) + ".",
            data=result,
        )


class AdminPaystackSettlementView(generics.GenericAPIView):
    """
    GET /admin-manager/analytics/paystack-settlements/

    The payouts Paystack actually made into the company bank account.

    This is the reality check on every other number: settlements are gross
    collections minus fees minus refunds and chargebacks, so they are the only
    figure that represents money that genuinely arrived. Read live from
    Paystack — nothing here is stored.

    Note this is *not* platform revenue. A settlement is mostly money held on
    behalf of vendors and riders, which then flows out as payouts. Platform
    revenue is the commission slice, reported by the endpoints above.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Paystack settlements (money that reached the bank)",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description='YYYY-MM-DD'),
            openapi.Parameter('status', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=['success', 'processing', 'pending', 'failed']),
        ],
        responses={200: 'Settlements', 401: 'Unauthorized'},
    )
    def get(self, request):
        from helpers.paystack import PaystackManager

        start, end, _period = resolve_window(request)
        ok, settlements = PaystackManager().settlements(
            start_date=start.date().isoformat() if start else None,
            end_date=end.date().isoformat() if end else None,
            status=request.GET.get('status') or None,
        )
        if not ok:
            return bad_request_response(
                message="Could not fetch settlements from Paystack.")

        rows = []
        total = Decimal('0')
        for entry in settlements:
            # Paystack reports settlement amounts in kobo.
            amount = Decimal(str(entry.get('amount') or 0)) / Decimal('100')
            total += amount
            rows.append({
                'id': entry.get('id'),
                'amount': float(amount),
                'currency': entry.get('currency') or 'NGN',
                'status': entry.get('status'),
                'settled_by': entry.get('settled_by'),
                'settlement_date': entry.get('settlement_date'),
                'created_at': entry.get('createdAt') or entry.get('created_at'),
            })

        return success_response(data={
            'summary': {
                'settlement_count': len(rows),
                'total_settled': float(total),
                'note': (
                    'Money Paystack paid into the company bank account. This is '
                    'gross float, not revenue — most of it is owed onward to '
                    'vendors and riders.'
                ),
            },
            'settlements': rows,
        })
