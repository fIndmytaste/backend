"""
Paystack fee capture
====================

Paystack never moves money for free. A collection is settled to us net of a
processing fee; a payout is debited with a transfer fee. Our own tables record
only the gross amounts, so "platform earnings" computed from `Order` is money
we billed, not money we kept.

This module turns Paystack's payloads into `PaystackFeeRecord` rows so the
dashboard can show, for any period:

    gross collected  →  Paystack fees  →  net settled
    platform earnings  −  Paystack fees  =  net platform revenue

Two grades of number live in that table, and the distinction matters:

  reported  – `fees` came from Paystack's own payload (charge webhook / verify
              response / balance ledger). Exact.
  estimated – the payload carried no fee, so we applied the published fee
              schedule below. Paystack's transfer objects routinely omit fees,
              so most payout rows start life estimated and are corrected later
              by `sync_payout_fees_from_ledger()`.

Every recorder is best-effort: a failure here must never break a payment. Call
sites wrap nothing — the functions swallow and log their own errors.
"""

from decimal import Decimal, ROUND_HALF_UP
import logging

from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')


# ---------------------------------------------------------------------------
# Fee schedule (fallback only — used when Paystack doesn't report a fee)
# ---------------------------------------------------------------------------
# Paystack's published Nigerian pricing. Override any of it in settings via
# PAYSTACK_FEE_SCHEDULE = {...} when your negotiated rate differs; keys are
# merged over these defaults, so you only state what changed.
DEFAULT_FEE_SCHEDULE = {
    # Card & most local channels: percentage + flat, flat waived below the
    # threshold, whole fee capped.
    'card': {
        'percentage': Decimal('0.015'),      # 1.5%
        'flat': Decimal('100'),              # ₦100
        'flat_waiver_below': Decimal('2500'),  # flat not applied under ₦2,500
        'cap': Decimal('2000'),              # fee never exceeds ₦2,000
    },
    # Bank transfer / dedicated virtual account (NUBAN) collections.
    'bank_transfer': {
        'percentage': Decimal('0.01'),       # 1%
        'flat': Decimal('0'),
        'flat_waiver_below': Decimal('0'),
        'cap': Decimal('300'),               # capped at ₦300
    },
    # Outbound transfers to bank accounts (vendor / rider payouts), tiered by
    # amount: (upper_bound_inclusive_or_None, fee).
    'payout_tiers': [
        (Decimal('5000'), Decimal('10')),
        (Decimal('50000'), Decimal('25')),
        (None, Decimal('50')),
    ],
}

# Channels that Paystack bills at the dedicated-account / bank-transfer rate.
_BANK_TRANSFER_CHANNELS = {'bank_transfer', 'dedicated_nuban', 'bank', 'ussd'}


def _schedule():
    """Fee schedule with any settings override merged over the defaults."""
    from django.conf import settings

    override = getattr(settings, 'PAYSTACK_FEE_SCHEDULE', None) or {}
    schedule = {key: dict(value) if isinstance(value, dict) else value
                for key, value in DEFAULT_FEE_SCHEDULE.items()}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(schedule.get(key), dict):
            schedule[key].update(value)
        else:
            schedule[key] = value
    return schedule


def _money(value):
    """Coerce anything Paystack hands us into a 2dp Decimal."""
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _kobo_to_naira(value):
    """Paystack speaks kobo everywhere; we store naira."""
    if value is None or value == '':
        return None
    try:
        return (Decimal(str(value)) / Decimal('100')).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return None


def estimate_collection_fee(amount, channel=None):
    """Fee Paystack would charge to collect `amount` naira on `channel`."""
    amount = _money(amount) or Decimal('0.00')
    schedule = _schedule()
    rule = (schedule['bank_transfer']
            if (channel or '').lower() in _BANK_TRANSFER_CHANNELS
            else schedule['card'])

    fee = amount * Decimal(str(rule['percentage']))
    if amount >= Decimal(str(rule.get('flat_waiver_below') or 0)):
        fee += Decimal(str(rule.get('flat') or 0))

    cap = rule.get('cap')
    if cap is not None:
        fee = min(fee, Decimal(str(cap)))
    return fee.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def estimate_payout_fee(amount):
    """Fee Paystack would charge to transfer `amount` naira to a bank account."""
    amount = _money(amount) or Decimal('0.00')
    for upper, fee in _schedule()['payout_tiers']:
        if upper is None or amount <= Decimal(str(upper)):
            return Decimal(str(fee)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return Decimal('0.00')


# ---------------------------------------------------------------------------
# Payload readers
# ---------------------------------------------------------------------------

def _unwrap(payload):
    """
    Accept any shape we store: a raw webhook body ({event, data}), a verify
    response ({status, data}), or an already-unwrapped data dict.
    """
    if not isinstance(payload, dict):
        return {}
    data = payload.get('data')
    return data if isinstance(data, dict) else payload


def _reported_fee(data):
    """
    Pull Paystack's own fee off a payload, in naira.

    Charges carry `fees` in kobo. Transfers, when they say anything at all, use
    `fee_charged`. `fees_split` appears on split/subaccount transactions and
    breaks the fee down — `fees_split.paystack` is the part Paystack keeps.
    """
    for key in ('fees', 'fee_charged', 'fee'):
        if data.get(key) not in (None, ''):
            fee = _kobo_to_naira(data.get(key))
            if fee is not None:
                return fee

    split = data.get('fees_split')
    if isinstance(split, dict) and split.get('paystack') not in (None, ''):
        return _kobo_to_naira(split.get('paystack'))
    return None


def _paid_at(data):
    for key in ('paid_at', 'paidAt', 'transaction_date', 'updatedAt', 'updated_at', 'createdAt', 'created_at'):
        raw = data.get(key)
        if not raw:
            continue
        try:
            parsed = parse_datetime(raw) if isinstance(raw, str) else raw
        except Exception:
            parsed = None
        if parsed:
            return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    return timezone.now()


def read_collection(payload):
    """
    Normalise a charge payload into the numbers we store.

    Returns a dict, or None when the payload carries no usable amount.
    """
    data = _unwrap(payload)
    gross = _kobo_to_naira(data.get('amount'))
    if gross is None:
        return None

    channel = data.get('channel') or (data.get('authorization') or {}).get('channel')
    fee = _reported_fee(data)
    is_estimated = fee is None
    if is_estimated:
        fee = estimate_collection_fee(gross, channel)

    return {
        'gross_amount': gross,
        'fee_amount': fee,
        'net_amount': (gross - fee).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'channel': channel,
        'currency': data.get('currency') or 'NGN',
        'reference': data.get('reference'),
        'paystack_id': str(data.get('id')) if data.get('id') is not None else None,
        'paid_at': _paid_at(data),
        'is_estimated': is_estimated,
    }


def read_payout(payload):
    """
    Normalise a transfer payload. `net_amount` here is the total debited from
    our Paystack balance: the amount the recipient gets plus the transfer fee.
    """
    data = _unwrap(payload)
    gross = _kobo_to_naira(data.get('amount'))
    if gross is None:
        return None

    fee = _reported_fee(data)
    is_estimated = fee is None
    if is_estimated:
        fee = estimate_payout_fee(gross)

    return {
        'gross_amount': gross,
        'fee_amount': fee,
        'net_amount': (gross + fee).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'channel': 'transfer',
        'currency': data.get('currency') or 'NGN',
        'reference': data.get('reference') or data.get('transfer_code'),
        'paystack_id': str(data.get('id')) if data.get('id') is not None else None,
        'paid_at': _paid_at(data),
        'is_estimated': is_estimated,
    }


# ---------------------------------------------------------------------------
# Recorders — safe to call from any payment path
# ---------------------------------------------------------------------------

def _record(direction, parsed, *, wallet_transaction=None, order=None,
            user=None, source='webhook', payload=None):
    from wallet.models import PaystackFeeRecord

    reference = parsed.get('reference')
    if not reference:
        logger.warning("Paystack %s fee not recorded: payload has no reference", direction)
        return None

    defaults = {
        'wallet_transaction': wallet_transaction,
        'order': order,
        'user': user,
        'paystack_id': parsed.get('paystack_id'),
        'channel': parsed.get('channel'),
        'currency': parsed.get('currency') or 'NGN',
        'gross_amount': parsed['gross_amount'],
        'fee_amount': parsed['fee_amount'],
        'net_amount': parsed['net_amount'],
        'is_estimated': parsed['is_estimated'],
        'source': 'estimate' if parsed['is_estimated'] else source,
        'paid_at': parsed.get('paid_at'),
        'raw_payload': payload,
    }
    # Never let a later payload blank out a link an earlier one established.
    existing = PaystackFeeRecord.objects.filter(
        direction=direction, reference=reference).first()
    if existing:
        for field in ('wallet_transaction', 'order', 'user'):
            if defaults[field] is None:
                defaults[field] = getattr(existing, field)
        # A reported fee always wins over an estimate we wrote earlier.
        if existing.is_estimated is False and parsed['is_estimated']:
            defaults.update({
                'fee_amount': existing.fee_amount,
                'net_amount': existing.net_amount,
                'is_estimated': False,
                'source': existing.source,
            })

    record, _created = PaystackFeeRecord.objects.update_or_create(
        direction=direction, reference=reference, defaults=defaults)
    return record


def record_collection_fee(payload, *, wallet_transaction=None, order=None,
                          user=None, source='webhook'):
    """
    Record what Paystack charged us to collect a payment. Idempotent on
    (collection, reference); never raises.
    """
    try:
        parsed = read_collection(payload)
        if not parsed:
            return None
        if order is None and wallet_transaction is not None:
            order = wallet_transaction.order
        if user is None and wallet_transaction is not None:
            user = wallet_transaction.user or (
                wallet_transaction.wallet.user if wallet_transaction.wallet_id else None)
        return _record('collection', parsed, wallet_transaction=wallet_transaction,
                       order=order, user=user, source=source, payload=payload)
    except Exception:
        logger.exception("Failed to record Paystack collection fee")
        return None


def record_payout_fee(payload, *, wallet_transaction=None, user=None,
                      source='webhook', direction='payout'):
    """
    Record what Paystack charged us to pay someone out. Idempotent on
    (payout, reference); never raises.
    """
    try:
        parsed = read_payout(payload)
        if not parsed:
            return None
        if user is None and wallet_transaction is not None:
            user = wallet_transaction.user or (
                wallet_transaction.wallet.user if wallet_transaction.wallet_id else None)
        return _record(direction, parsed, wallet_transaction=wallet_transaction,
                       user=user, source=source, payload=payload)
    except Exception:
        logger.exception("Failed to record Paystack payout fee")
        return None


# ---------------------------------------------------------------------------
# Reconciliation against Paystack's balance ledger
# ---------------------------------------------------------------------------

def sync_payout_fees_from_ledger(start_date=None, end_date=None, page_size=100,
                                 max_pages=20):
    """
    Replace estimated fees with Paystack's actual ones.

    The balance ledger is the only endpoint that reports the fee on every
    movement, including transfers. Walk it and correct any row we estimated.

    Returns {'scanned': n, 'updated': n, 'created': n}.
    """
    from helpers.paystack import PaystackManager
    from wallet.models import PaystackFeeRecord

    stats = {'scanned': 0, 'updated': 0, 'created': 0}
    manager = PaystackManager()

    for page in range(1, max_pages + 1):
        ok, entries = manager.balance_ledger(
            page=page, per_page=page_size,
            start_date=start_date, end_date=end_date,
        )
        if not ok or not entries:
            break

        for entry in entries:
            stats['scanned'] += 1
            fee = _kobo_to_naira(entry.get('fees'))
            if fee is None:
                continue

            reference = (entry.get('reference')
                         or (entry.get('transfer') or {}).get('reference')
                         or str(entry.get('id') or ''))
            if not reference:
                continue

            # Ledger amounts are signed: negative means money left the balance.
            raw_amount = _kobo_to_naira(entry.get('amount')) or Decimal('0.00')
            direction = 'payout' if raw_amount < 0 else 'collection'
            gross = abs(raw_amount)

            record = PaystackFeeRecord.objects.filter(
                direction=direction, reference=reference).first()
            if record is None:
                PaystackFeeRecord.objects.create(
                    direction=direction,
                    reference=reference,
                    paystack_id=str(entry.get('id')) if entry.get('id') is not None else None,
                    channel='transfer' if direction == 'payout' else entry.get('domain'),
                    currency=entry.get('currency') or 'NGN',
                    gross_amount=gross,
                    fee_amount=fee,
                    net_amount=(gross + fee) if direction == 'payout' else (gross - fee),
                    is_estimated=False,
                    source='balance_ledger',
                    paid_at=_paid_at(entry),
                    raw_payload=entry,
                )
                stats['created'] += 1
                continue

            if record.is_estimated or record.fee_amount != fee:
                record.fee_amount = fee
                record.net_amount = (
                    (record.gross_amount + fee) if direction == 'payout'
                    else (record.gross_amount - fee)
                )
                record.is_estimated = False
                record.source = 'balance_ledger'
                record.save(update_fields=[
                    'fee_amount', 'net_amount', 'is_estimated', 'source', 'updated_at'])
                stats['updated'] += 1

        if len(entries) < page_size:
            break

    return stats
