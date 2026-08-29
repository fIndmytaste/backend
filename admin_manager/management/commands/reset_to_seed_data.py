"""Clear operational data, keeping configuration and a few seed accounts.

Deliberately conservative: it deletes by explicit model list rather than
truncating, so a table nobody thought about is left alone rather than silently
emptied. Run without --execute first; that reports exactly what would go.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

# Accounts that survive. Everything else, and everything hanging off it, goes.
KEEP_EMAILS = [
    'admin@findmytaste.com.ng',      # superuser
    'maria1@gmail.com',              # vendor
    'augustinevickky+11@gmail.com',  # rider
    'tester@gmail.com',              # buyer / store review account
]

# Operational data: wiped wholesale regardless of who it belongs to.
PURGE_MODELS = [
    'product.OrderItemVariant',
    'product.OrderItem',
    'product.DeclinedOrder',
    'product.DeliveryTracking',
    'rider.DeliveryTracking',
    'product.Order',
    'product.DeliveryFee',
    'product.PromoUsage',
    'product.ProductView',
    'product.Rating',
    'product.UserFavoriteVendor',
    'wallet.PaystackFeeRecord',
    'wallet.WalletTransaction',
    'account.Notification',
    'account.PushNotificationLog',
    'account.VerificationCode',
    'account.FCMToken',
    'account.VendorRating',
    'account.RiderRating',
    'account.VendorIssueReporting',
    'account.VirtualAccount',
    'admin_manager.AnnouncementView',
    'admin_manager.PopupAnnouncementView',
]

# Configuration and content that must survive, recorded so the report can
# prove they were untouched.
PRESERVE_MODELS = [
    'product.SystemCategory',
    'product.VendorCategory',
    'vendor.MarketPlace',
    'product.DeliveryZone',
    'helpers.DeliveryConfiguration',
    'product.PlatformSettings',
    'product.EstateGatePass',
    'product.PromoCode',
    'admin_manager.Announcement',
    'admin_manager.PopupAnnouncement',
    'admin_manager.AnnouncementImage',
    'admin_manager.AnnouncementLink',
]


class Command(BaseCommand):
    help = "Clear operational data, keeping config and the seed accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute', action='store_true',
            help='Actually delete. Without this the command only reports.',
        )

    def handle(self, *args, **options):
        from django.apps import apps
        from account.models import User, Vendor, Rider
        from wallet.models import Wallet

        execute = options['execute']
        keep_users = User.objects.filter(email__in=KEEP_EMAILS)
        keep_ids = list(keep_users.values_list('id', flat=True))

        missing = set(KEEP_EMAILS) - set(keep_users.values_list('email', flat=True))
        if missing:
            self.stderr.write(self.style.ERROR(
                'Refusing to run: these accounts do not exist: %s' % ', '.join(sorted(missing))
            ))
            return

        doomed_users = User.objects.exclude(id__in=keep_ids)

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Accounts kept'))
        for u in keep_users.order_by('email'):
            self.stdout.write('  %-32s role=%-7s super=%s' % (u.email, u.role, u.is_superuser))

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Operational data to clear'))
        total = 0
        for label in PURGE_MODELS:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            n = model.objects.count()
            total += n
            if n:
                self.stdout.write('  %-38s %d' % (label, n))
        self.stdout.write('  %-38s %d' % ('TOTAL ROWS', total))

        # A rider who also carries a stray Vendor row keeps the Rider only.
        stray_vendors = Vendor.objects.filter(user__id__in=keep_ids).exclude(user__role='vendor')

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Accounts to delete (cascades to their data)'))
        self.stdout.write('  users            %d  (of %d)' % (doomed_users.count(), User.objects.count()))
        self.stdout.write('  vendors          %d' % Vendor.objects.exclude(user__id__in=keep_ids).count())
        self.stdout.write('  riders           %d' % Rider.objects.exclude(user__id__in=keep_ids).count())
        self.stdout.write('  stray vendor rows on kept accounts: %d' % stray_vendors.count())

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Configuration preserved (untouched)'))
        for label in PRESERVE_MODELS:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            self.stdout.write('  %-38s %d' % (label, model.objects.count()))

        if not execute:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Dry run. Re-run with --execute to apply.'))
            return

        with transaction.atomic():
            for label in PURGE_MODELS:
                try:
                    model = apps.get_model(label)
                except LookupError:
                    continue
                model.objects.all().delete()

            stray_vendors.delete()
            doomed_users.delete()

            # Kept accounts start from zero rather than carrying old figures.
            Wallet.objects.update(balance=0)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Done.'))
        self.stdout.write('  users remaining    %d' % User.objects.count())
        self.stdout.write('  vendors remaining  %d' % Vendor.objects.count())
        self.stdout.write('  riders remaining   %d' % Rider.objects.count())
