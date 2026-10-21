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


def withdrawal_narration(transaction_obj, reason=None):
    """'Find My Taste withdrawal WTD-1A2B3C' -- purpose and reference included."""
    purpose = (reason or '').strip()
    if purpose.lower() in GENERIC_REASONS:
        purpose = 'withdrawal'
    reference = getattr(transaction_obj, 'reference_code', None) or ''
    narration = f"{BRAND} {purpose} {reference}".strip()
    return narration[:MAX_NARRATION_LENGTH]


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
    narration = data.get('reason') or withdrawal_narration(
        transaction_obj, transaction_obj.description)

    return {
        'brand': BRAND,
        'title': 'Withdrawal receipt',
        'reference': transaction_obj.reference_code,
        'transfer_reference': transaction_obj.external_reference or None,
        'narration': narration,
        'amount': str(transaction_obj.amount),
        'currency': 'NGN',
        'recipient_name': (user.full_name if user else None) or None,
        'bank_name': bank.get('bank_name') or None,
        'account_name': bank.get('account_name') or None,
        'account_number_masked': mask_account_number(bank.get('account_number')) or None,
        'requested_at': transaction_obj.created_at.isoformat() if transaction_obj.created_at else None,
        'updated_at': transaction_obj.updated_at.isoformat() if transaction_obj.updated_at else None,
    }
