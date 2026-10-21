"""
Rider rewards: pay a bonus when a rider hits a delivery target in a period.

`evaluate_rider_rewards()` runs on a schedule (see CELERY_BEAT_SCHEDULE). For
every active programme it looks at the current period, and also the one that
just ended so deliveries in its final minutes are not missed, counts each
rider's completed deliveries, and credits the bonus to the rider's wallet once
per rider per period. The unique constraint on RiderRewardAward makes a
double payment impossible even if two runs overlap.
"""

import logging
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def _window_bounds(start_date, end_date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end = timezone.make_aware(datetime.combine(end_date, time.max), tz)
    return start, end


def delivered_counts(start_date, end_date, rider_ids=None):
    """{rider_id: completed deliveries} within the inclusive date window."""
    from product.models import Order

    start, end = _window_bounds(start_date, end_date)
    qs = Order.objects.filter(status='delivered', rider__isnull=False).filter(
        Q(delivered_at__range=(start, end))
        | Q(delivered_at__isnull=True, actual_delivery_time__range=(start, end))
    )
    if rider_ids is not None:
        qs = qs.filter(rider_id__in=rider_ids)
    return {
        row['rider_id']: row['total']
        for row in qs.values('rider_id').annotate(total=Count('id'))
    }


def windows_to_check(program, today):
    """Current period plus the previous one, de-duplicated, never in the future."""
    if program.period == 'custom':
        if not program.start_date or not program.end_date:
            return []
        if program.start_date > today or program.end_date < today - timedelta(days=1):
            return []
        return [(program.start_date, program.end_date)]

    windows = []
    for day in (today, today - timedelta(days=1)):
        window = program.current_window(day)
        if window not in windows:
            windows.append(window)
    return windows


def award_bonus(program, rider, period_start, period_end, deliveries):
    """Credit one bonus. Returns the award, or None if already paid."""
    from account.models import Notification
    from admin_manager.models import RiderRewardAward
    from wallet.models import Wallet, WalletTransaction

    try:
        with transaction.atomic():
            award = RiderRewardAward.objects.create(
                program=program,
                rider=rider,
                period_start=period_start,
                period_end=period_end,
                deliveries_counted=deliveries,
                amount=program.bonus_amount,
            )
            wallet, _ = Wallet.objects.select_for_update().get_or_create(user=rider.user)
            txn = WalletTransaction.objects.create(
                wallet=wallet,
                user=rider.user,
                amount=program.bonus_amount,
                transaction_type='reward',
                status='completed',
                description=f"Rider reward: {program.name} ({deliveries} deliveries)",
            )
            wallet.deposit(program.bonus_amount)
            award.wallet_transaction = txn
            award.save(update_fields=['wallet_transaction'])
    except IntegrityError:
        return None

    title = 'You earned a bonus! 🎉'
    body = (
        f"You completed {deliveries} deliveries and earned ₦{program.bonus_amount:,.0f} "
        f"from {program.name}. It has been added to your wallet."
    )
    try:
        from helpers.push_notification import notification_helper
        Notification.objects.create(user=rider.user, title=title, content=body)
        notification_helper.send_to_user_async(
            user=rider.user, title=title, body=body, data={'type': 'rider_reward'})
    except Exception as error:
        logger.warning('Reward notification failed for rider %s: %s', rider.id, error)
    return award


def evaluate_rider_rewards(today=None):
    from account.models import Rider
    from admin_manager.models import RiderRewardAward, RiderRewardProgram

    today = today or timezone.localdate()
    paid = 0
    for program in RiderRewardProgram.objects.filter(is_active=True):
        riders = Rider.objects.select_related('user').filter(user__is_active=True)
        if not program.include_in_house_riders:
            riders = riders.filter(is_in_house_rider=False)
        riders_by_id = {rider.id: rider for rider in riders}
        if not riders_by_id:
            continue

        for period_start, period_end in windows_to_check(program, today):
            counts = delivered_counts(period_start, period_end, rider_ids=list(riders_by_id))
            already = set(RiderRewardAward.objects.filter(
                program=program, period_start=period_start,
            ).values_list('rider_id', flat=True))
            for rider_id, total in counts.items():
                if total < program.target_deliveries or rider_id in already:
                    continue
                if award_bonus(program, riders_by_id[rider_id], period_start, period_end, total):
                    paid += 1
    if paid:
        logger.info('Rider rewards run paid %s bonus(es).', paid)
    return paid


def rider_reward_progress(rider, today=None):
    """What the rider app shows: each active programme and how close they are."""
    from admin_manager.models import RiderRewardAward, RiderRewardProgram

    today = today or timezone.localdate()
    progress = []
    programs = RiderRewardProgram.objects.filter(is_active=True)
    if rider.is_in_house_rider:
        programs = programs.filter(include_in_house_riders=True)
    for program in programs:
        start, end = program.current_window(today)
        if not start or not end or start > today or end < today:
            continue
        done = delivered_counts(start, end, rider_ids=[rider.id]).get(rider.id, 0)
        earned = RiderRewardAward.objects.filter(
            program=program, rider=rider, period_start=start).exists()
        progress.append({
            'id': str(program.id),
            'name': program.name,
            'description': program.description,
            'target_deliveries': program.target_deliveries,
            'completed_deliveries': done,
            'remaining_deliveries': max(program.target_deliveries - done, 0),
            'bonus_amount': str(program.bonus_amount),
            'period': program.period,
            'period_start': start.isoformat(),
            'period_end': end.isoformat(),
            'earned': earned,
        })
    return progress
