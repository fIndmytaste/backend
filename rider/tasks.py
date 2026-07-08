import logging
from decimal import Decimal

from celery import shared_task
from django.db import transaction as db_transaction

logger = logging.getLogger(__name__)

# Riders are paid out weekly for any balance at or above this amount.
# Configurable via DeliveryConfiguration key 'rider_weekly_payout_minimum'.
DEFAULT_WEEKLY_PAYOUT_MINIMUM = Decimal('1000.00')


def get_weekly_payout_minimum():
    from helpers.models import ConfigurationManager
    try:
        configured = ConfigurationManager.get_config(
            'rider_weekly_payout_minimum', int(DEFAULT_WEEKLY_PAYOUT_MINIMUM))
        return Decimal(str(configured))
    except Exception:
        return DEFAULT_WEEKLY_PAYOUT_MINIMUM


def process_rider_payout(rider, amount=None, description='Weekly payout'):
    """
    Pay out a rider's wallet balance (or a specific amount) to their bank account.
    Holds the funds, initiates a Paystack transfer and returns (success, message).
    A failed initiation releases the held funds again.
    """
    from helpers.paystack import PaystackManager
    from wallet.models import Wallet, WalletTransaction

    wallet, _ = Wallet.objects.get_or_create(user=rider.user)
    payout_amount = Decimal(str(amount)) if amount is not None else wallet.balance

    if payout_amount <= 0:
        return False, 'Nothing to pay out.'
    if wallet.balance < payout_amount:
        return False, 'Insufficient balance.'

    with db_transaction.atomic():
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            user=rider.user,
            amount=payout_amount,
            transaction_type='withdrawal',
            status='pending',
            description=description,
        )
        wallet.withdraw(payout_amount)

    success, message = PaystackManager().initiate_transfer(
        user=rider.user,
        vendor=None,
        amount=payout_amount,
        transaction_obj=txn,
        reason=description,
    )
    if not success:
        txn.status = 'failed'
        txn.save()
        wallet.refresh_from_db()
        wallet.deposit(payout_amount)
    return success, message


@shared_task(name='rider.process_weekly_rider_payouts')
def process_weekly_rider_payouts():
    """
    Weekly payout run: pays every active independent rider their accumulated
    wallet balance. In-house (salaried) riders are skipped. Scheduled via
    celery beat (see CELERY_BEAT_SCHEDULE in settings).
    """
    from account.models import Rider
    from wallet.models import Wallet

    minimum = get_weekly_payout_minimum()
    riders = Rider.objects.filter(is_in_house_rider=False).select_related('user')

    paid, skipped, failed = [], [], []
    for rider in riders:
        wallet = Wallet.objects.filter(user=rider.user).first()
        if not wallet or wallet.balance < minimum:
            skipped.append(str(rider.id))
            continue

        try:
            success, message = process_rider_payout(rider, description='Weekly payout')
        except Exception as error:
            logger.exception('Weekly payout error for rider %s: %s', rider.id, error)
            failed.append({'rider_id': str(rider.id), 'reason': str(error)})
            continue

        if success:
            paid.append(str(rider.id))
            try:
                from account.models import Notification
                from helpers.push_notification import notification_helper
                title = 'Weekly payout on the way'
                body = 'Your weekly earnings payout has been initiated and will arrive in your bank account shortly.'
                Notification.objects.create(user=rider.user, title=title, content=body)
                notification_helper.send_to_user_async(
                    user=rider.user,
                    title=title,
                    body=body,
                    data={'type': 'weekly_payout'},
                )
            except Exception as notify_error:
                logger.warning('Weekly payout notification failed for rider %s: %s', rider.id, notify_error)
        else:
            failed.append({'rider_id': str(rider.id), 'reason': message})

    summary = {
        'paid': paid,
        'failed': failed,
        'skipped_count': len(skipped),
        'minimum': str(minimum),
    }
    logger.info('Weekly rider payout run complete: %s', summary)
    return summary
