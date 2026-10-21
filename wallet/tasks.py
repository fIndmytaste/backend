"""
Automatic vendor payouts.

Vendors with `auto_payout_enabled` (switched on by an admin, either on the
vendor's request or on their behalf) have their cleared balance paid to their
bank account every day. Only money past the settlement hold is sent, and
nothing goes out below the vendor minimum withdrawal, the same rules a manual
withdrawal follows.
"""

import logging
from decimal import Decimal

from celery import shared_task
from django.db import transaction as db_transaction

logger = logging.getLogger(__name__)


def pay_out_vendor(vendor):
    """Send one vendor's cleared balance. Returns (success, message)."""
    from helpers.paystack import PaystackManager
    from wallet.models import Wallet, WalletTransaction
    from wallet.serializers import get_minimum_withdrawal_for_user
    from wallet.settlement import to_amount, withdrawable_balance

    user = vendor.user
    if not ((vendor.bank_account and vendor.bank_name) or (user.bank_account and user.bank_name)):
        return False, 'No bank details on file.'

    with db_transaction.atomic():
        wallet = Wallet.objects.select_for_update().filter(user=user).first()
        if wallet is None:
            return False, 'No wallet.'
        amount = to_amount(min(withdrawable_balance(wallet), wallet.balance))
        minimum = Decimal(str(get_minimum_withdrawal_for_user(user)))
        if amount <= 0 or amount < minimum:
            return False, f'Cleared balance {amount} is below the minimum {minimum}.'

        txn = WalletTransaction.objects.create(
            wallet=wallet,
            user=user,
            amount=amount,
            transaction_type='withdrawal',
            status='pending',
            description='Automatic payout',
        )
        wallet.withdraw(amount)

    success, message = PaystackManager().initiate_transfer(
        user=user,
        vendor=vendor,
        amount=amount,
        transaction_obj=txn,
        reason='automatic payout',
    )
    if not success:
        txn.status = 'failed'
        txn.save(update_fields=['status', 'updated_at'])
        wallet.refresh_from_db()
        wallet.deposit(amount)
        return False, message

    try:
        from account.models import Notification
        from helpers.push_notification import notification_helper
        title = 'Payout on the way'
        body = f'₦{amount:,.2f} is on its way to your bank account (automatic payout).'
        Notification.objects.create(user=user, title=title, content=body)
        notification_helper.send_to_user_async(
            user=user, title=title, body=body, data={'type': 'auto_payout'})
    except Exception as error:
        logger.warning('Auto payout notification failed for vendor %s: %s', vendor.id, error)
    return True, message


@shared_task(name='wallet.process_vendor_auto_payouts')
def process_vendor_auto_payouts():
    from account.models import Vendor

    paid, skipped, failed = [], 0, []
    vendors = Vendor.objects.select_related('user').filter(
        auto_payout_enabled=True, user__is_active=True)
    for vendor in vendors:
        try:
            success, message = pay_out_vendor(vendor)
        except Exception as error:
            logger.exception('Auto payout error for vendor %s', vendor.id)
            failed.append({'vendor_id': str(vendor.id), 'reason': str(error)})
            continue
        if success:
            paid.append(str(vendor.id))
        elif 'below the minimum' in message or message in ('No wallet.',):
            skipped += 1
        else:
            failed.append({'vendor_id': str(vendor.id), 'reason': message})

    summary = {'paid': paid, 'failed': failed, 'skipped_count': skipped}
    logger.info('Vendor auto payout run complete: %s', summary)
    return summary
