"""
Vendor payout clearing.

Paystack settles a collection into our own balance roughly 24 hours after the
customer pays. Until that happens the money is not ours to move, so a vendor
earning that already shows in their wallet is not yet something we can
transfer out. This module draws the line between the *balance* (everything a
vendor has earned) and the *withdrawable balance* (what we can actually pay
them today).

Crediting is unchanged: an earning still lands in the wallet the moment the
order is settled, so vendors keep seeing their money accrue in real time. What
changes is that an earning stays held until its order is older than
SETTLEMENT_HOLD_HOURS, and held money cannot be withdrawn.

Riders are deliberately out of scope — their payout rules live in the rider
app and are not affected by this hold.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Min, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

SETTLEMENT_HOLD_HOURS = 24

ZERO = Decimal('0.00')


def to_amount(value):
    """Coerce anything money-shaped into a 2dp Decimal."""
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def user_is_vendor(user):
    from account.models import Vendor

    return Vendor.objects.filter(user=user).exists()


def held_earnings_queryset(user, now=None):
    """
    Earnings that have not cleared yet.

    An earning clears SETTLEMENT_HOLD_HOURS after its order was placed, since
    that is when the customer paid and therefore when Paystack settles us.
    Earnings with no order attached (manual credits, adjustments) fall back to
    when the credit itself was written.
    """
    from wallet.models import WalletTransaction

    cutoff = (now or timezone.now()) - timedelta(hours=SETTLEMENT_HOLD_HOURS)
    # Older earning rows were written with only `wallet` set and `user` left
    # null. Matching on both is what the admin revenue dashboard does, and
    # missing those rows here would quietly let held money be withdrawn.
    belongs_to_user = Q(user=user) | Q(user__isnull=True, wallet__user=user)
    return WalletTransaction.objects.filter(
        belongs_to_user,
        transaction_type='earning',
        status='completed',
    ).annotate(
        clears_from=Coalesce('order__created_at', 'created_at'),
    ).filter(clears_from__gt=cutoff)


def held_amount(user, now=None):
    """Total still under the settlement hold for this user."""
    if not user_is_vendor(user):
        return ZERO
    total = held_earnings_queryset(user, now).aggregate(total=Sum('amount'))['total']
    return to_amount(total)


def next_clearance_at(user, now=None):
    """When the oldest held earning becomes withdrawable, or None if nothing is held."""
    if not user_is_vendor(user):
        return None
    earliest = held_earnings_queryset(user, now).aggregate(
        earliest=Min('clears_from'),
    )['earliest']
    if not earliest:
        return None
    return earliest + timedelta(hours=SETTLEMENT_HOLD_HOURS)


def withdrawable_balance(wallet, now=None):
    """
    The part of the wallet balance a vendor may withdraw right now.

    Withdrawals already debit the balance, so subtracting the currently held
    earnings from the live balance is enough — no separate ledger is needed.
    Clamped at zero to stay truthful for balances that predate this hold, where
    a vendor may already have withdrawn against uncleared earnings.
    """
    balance = to_amount(wallet.balance)
    held = held_amount(wallet.user, now)
    if held <= ZERO:
        return balance
    return max(ZERO, balance - held)


def settlement_summary(wallet, now=None):
    """API-shaped view of the balance split, safe to expose to the vendor app."""
    now = now or timezone.now()
    balance = to_amount(wallet.balance)
    held = held_amount(wallet.user, now)
    available = max(ZERO, balance - held) if held > ZERO else balance
    clears_at = next_clearance_at(wallet.user, now) if held > ZERO else None

    return {
        'available_balance': str(available),
        'pending_clearance': str(held),
        'clearance_hold_hours': SETTLEMENT_HOLD_HOURS,
        'next_clearance_at': clears_at.isoformat() if clears_at else None,
    }
