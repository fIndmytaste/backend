"""
Withdrawal receipts and bank narrations.

Riders and vendors were getting withdrawals with a bare "Withdrawal from
balance" narration and no receipt to show. These helpers give every payout:

* a bank narration (Paystack's transfer `reason`) that names Find My Taste, the
  purpose and the receipt reference, and
* a `receipt` block on the wallet transaction that the apps render as a
  branded receipt.
"""

from account.models import Vendor

BRAND = 'Find My Taste'

# Paystack keeps the reason short on many bank statements; stay well inside.
MAX_NARRATION_LENGTH = 100

GENERIC_REASONS = {'', 'withdrawal from balance', 'withdrawal from wallet'}


def _role_word(user):
    role = getattr(user, 'role', None)
    return role if role in ('rider', 'vendor') else ''


def _naira(amount):
    try:
        return f"NGN {float(amount):,.2f}"
    except (TypeError, ValueError):
        return ''


def withdrawal_narration(transaction_obj, reason=None):
    """
    Bank narration (Paystack's transfer reason), e.g.
    'Find My Taste rider withdrawal NGN 15,000.00 ref WTD-1A2B3C'.
    Says who paid, for whom, how much and the reference on the receipt.
    """
    purpose = (reason or '').strip()
    if purpose.lower() in GENERIC_REASONS:
        purpose = 'withdrawal'
    user = getattr(transaction_obj, 'user', None)
    reference = getattr(transaction_obj, 'reference_code', None) or ''
    parts = [BRAND, _role_word(user), purpose, _naira(transaction_obj.amount),
             f"ref {reference}" if reference else '']
    narration = ' '.join(p for p in parts if p)
    return narration[:MAX_NARRATION_LENGTH]


def receipt_narration(transaction_obj, user, bank):
    """
    The plain-language line shown on the receipt, e.g.
    'Withdrawal of NGN 15,000.00 from your Find My Taste rider wallet to
    KEMI ADE, GTBank ****6789 on 24 Oct 2026, 10:15 AM. Ref WTD-1A2B3C.'
    """
    from django.utils import timezone

    role = _role_word(user)
    wallet = f"{BRAND} {role} wallet" if role else f"{BRAND} wallet"
    sentence = f"Withdrawal of {_naira(transaction_obj.amount)} from your {wallet}"

    destination = ', '.join(p for p in (
        bank.get('account_name'),
        ' '.join(p for p in (
            bank.get('bank_name'),
            mask_account_number(bank.get('account_number'))) if p),
    ) if p)
    if destination:
        sentence += f" to {destination}"
    if transaction_obj.created_at:
        when = timezone.localtime(transaction_obj.created_at)
        sentence += f" on {when.strftime('%-d %b %Y, %-I:%M %p')}"
    sentence += '.'
    if transaction_obj.reference_code:
        sentence += f" Ref {transaction_obj.reference_code}."
    return sentence


def mask_account_number(number):
    digits = str(number or '').strip()
    if len(digits) <= 4:
        return digits
    return '•' * (len(digits) - 4) + digits[-4:]


def _recipient_from_paystack(response_data):
    """Bank details Paystack reported for the transfer, when present."""
    if not isinstance(response_data, dict):
        return {}
    data = response_data.get('data') if isinstance(response_data.get('data'), dict) else response_data
    recipient = data.get('recipient') if isinstance(data, dict) else None
    details = recipient.get('details') if isinstance(recipient, dict) else None
    if not isinstance(details, dict):
        return {}
    return {
        'bank_name': details.get('bank_name'),
        'account_number': details.get('account_number'),
        'account_name': details.get('account_name') or (recipient or {}).get('name'),
    }


def _saved_bank_details(user):
    """Where payouts go today: a vendor's own copy when filled in, else the user record."""
    if user is None:
        return {}
    vendor = Vendor.objects.filter(user=user).only(
        'bank_name', 'bank_account', 'bank_account_name').first()
    if vendor and vendor.bank_name and vendor.bank_account:
        return {
            'bank_name': vendor.bank_name,
            'account_number': vendor.bank_account,
            'account_name': vendor.bank_account_name,
        }
    return {
        'bank_name': user.bank_name,
        'account_number': user.bank_account,
        'account_name': user.bank_account_name,
    }


def build_withdrawal_receipt(transaction_obj):
    """Receipt payload for a withdrawal transaction, or None for other types."""
    if transaction_obj.transaction_type != 'withdrawal':
        return None

    user = transaction_obj.user or (
        transaction_obj.wallet.user if transaction_obj.wallet_id and transaction_obj.wallet else None
    )
    response_data = transaction_obj.response_data if isinstance(transaction_obj.response_data, dict) else {}

    bank = _recipient_from_paystack(response_data) or _saved_bank_details(user)

    data = response_data.get('data') if isinstance(response_data.get('data'), dict) else {}
    # What the bank statement shows (the reason Paystack sent), kept for
    # matching; the receipt itself shows the plain-language narration.
    bank_narration = data.get('reason') or withdrawal_narration(
        transaction_obj, transaction_obj.description)

    return {
        'brand': BRAND,
        'title': 'Withdrawal receipt',
        'reference': transaction_obj.reference_code,
        'transfer_reference': transaction_obj.external_reference or None,
        'narration': receipt_narration(transaction_obj, user, bank),
        'bank_narration': bank_narration,
        'amount': str(transaction_obj.amount),
        'currency': 'NGN',
        'recipient_name': (user.full_name if user else None) or None,
        'bank_name': bank.get('bank_name') or None,
        'account_name': bank.get('account_name') or None,
        'account_number_masked': mask_account_number(bank.get('account_number')) or None,
        'requested_at': transaction_obj.created_at.isoformat() if transaction_obj.created_at else None,
        'updated_at': transaction_obj.updated_at.isoformat() if transaction_obj.updated_at else None,
    }
