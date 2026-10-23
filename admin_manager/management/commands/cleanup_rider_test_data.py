"""
Remove everything seed_rider_test_data created.

    python manage.py cleanup_rider_test_data --email akakurup@yahoo.com
    python manage.py cleanup_rider_test_data --email akakurup@yahoo.com --dry-run

Removes only [QA-TEST] data: the QA customer and vendor (with their product
and every order of the QA vendor), the [QA-TEST] reward with its payouts,
the test withdrawal receipts and related notifications. A test reward bonus
that was credited to the rider's wallet is taken back out again. Real
orders, transactions and settings are never touched.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from admin_manager.management.commands.seed_rider_test_data import (
    QA_CUSTOMER_EMAIL,
    QA_TAG,
    QA_VENDOR_EMAIL,
)


class Command(BaseCommand):
    help = 'Delete the [QA-TEST] data created by seed_rider_test_data.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help="The rider's account email.")
        parser.add_argument('--dry-run', action='store_true', help='Only show what would be removed.')

    def handle(self, *args, **options):
        from account.models import Notification, Rider, User
        from admin_manager.models import RiderRewardAward, RiderRewardProgram
        from product.models import Order, Product
        from wallet.models import Wallet, WalletTransaction

        rider = Rider.objects.select_related('user').filter(
            user__email__iexact=options['email']).first()
        if rider is None:
            raise CommandError(f"No rider account for {options['email']}.")

        orders = Order.objects.filter(vendor__user__email=QA_VENDOR_EMAIL)
        programs = RiderRewardProgram.objects.filter(name__startswith=QA_TAG)
        awards = RiderRewardAward.objects.filter(program__in=programs).select_related('wallet_transaction')
        receipts = WalletTransaction.objects.filter(
            user=rider.user, description__startswith=QA_TAG)
        reward_txns = WalletTransaction.objects.filter(
            pk__in=[a.wallet_transaction_id for a in awards if a.wallet_transaction_id])
        notifications = Notification.objects.filter(user=rider.user, content__contains=QA_TAG)
        qa_users = User.objects.filter(email__in=[QA_CUSTOMER_EMAIL, QA_VENDOR_EMAIL])
        credited = sum(
            (t.amount for t in reward_txns if t.status == 'completed'), Decimal('0'))

        self.stdout.write(f'Rider: {rider.user.email}')
        self.stdout.write(f'  orders:               {orders.count()}')
        self.stdout.write(f'  reward programmes:    {programs.count()} (payouts: {awards.count()})')
        self.stdout.write(f'  test receipts:        {receipts.count()}')
        self.stdout.write(f'  reward transactions:  {reward_txns.count()} (NGN {credited} to take back)')
        self.stdout.write(f'  notifications:        {notifications.count()}')
        self.stdout.write(f'  QA accounts:          {qa_users.count()}')
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run: nothing deleted.'))
            return

        with transaction.atomic():
            if credited:
                wallet = Wallet.objects.select_for_update().get(user=rider.user)
                taken = min(credited, wallet.balance)
                wallet.balance -= taken
                wallet.save(update_fields=['balance', 'updated_at'])
                if taken < credited:
                    self.stdout.write(self.style.WARNING(
                        f'Only NGN {taken} of the NGN {credited} test bonus was still in the '
                        'wallet; the rest had already been withdrawn.'))
            notifications.delete()
            awards.delete()
            reward_txns.delete()
            programs.delete()
            receipts.delete()
            orders.delete()
            Product.objects.filter(vendor__user__email=QA_VENDOR_EMAIL).delete()
            qa_users.delete()

        self.stdout.write(self.style.SUCCESS('All [QA-TEST] data removed.'))
