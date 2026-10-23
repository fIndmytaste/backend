"""
Create test data so a rider account can try the new rider-app features.

    python manage.py seed_rider_test_data --email akakurup@yahoo.com
    python manage.py cleanup_rider_test_data --email akakurup@yahoo.com

What it creates (all removable with cleanup_rider_test_data):
* a QA customer and a QA vendor (inactive and unapproved, so real customers
  can never see or order from it), with one product;
* orders assigned to the rider: 8 delivered this week, 1 accepted waiting
  for pickup, 1 on its way to the customer. Distances show in km;
* a "[QA-TEST]" weekly reward: 10 deliveries -> bonus. The rider starts at
  8/10, so finishing the two open orders earns it;
* two withdrawal receipts (one paid, one pending). Display only: they do not
  touch the wallet balance or move any money.

Nothing is left open for other riders: every order is already assigned to
this rider, never broadcast as "available".
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

QA_TAG = '[QA-TEST]'
QA_DOMAIN = 'qa-test.findmytaste.ng'
QA_CUSTOMER_EMAIL = f'qa-customer@{QA_DOMAIN}'
QA_VENDOR_EMAIL = f'qa-vendor@{QA_DOMAIN}'

# Lekki Phase 1, Lagos, and nearby drop-offs (a few km away).
VENDOR_LOCATION = ('6.4474', '3.4730')
DROP_OFFS = [
    ('Admiralty Way, Lekki Phase 1', Decimal('6.4410'), Decimal('3.4550')),
    ('Victoria Island, Adeola Odeku St', Decimal('6.4281'), Decimal('3.4219')),
    ('Ikoyi, Bourdillon Rd', Decimal('6.4550'), Decimal('3.4330')),
    ('Oniru, Lekki', Decimal('6.4352'), Decimal('3.4520')),
]


class Command(BaseCommand):
    help = 'Create [QA-TEST] orders, a reward and receipts for a rider to test with.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help="The rider's account email.")
        parser.add_argument('--bonus', default='2000', help='Reward bonus in naira (default 2000).')

    @transaction.atomic
    def handle(self, *args, **options):
        from account.models import Rider, User, Vendor
        from admin_manager.models import RiderRewardProgram
        from product.models import Order, OrderItem, Product, VendorCategory
        from wallet.models import Wallet, WalletTransaction

        rider = Rider.objects.select_related('user').filter(
            user__email__iexact=options['email']).first()
        if rider is None:
            raise CommandError(f"No rider account for {options['email']}.")
        if Order.objects.filter(vendor__user__email=QA_VENDOR_EMAIL, rider=rider).exists():
            raise CommandError(
                'Test data already exists for this rider. Run cleanup_rider_test_data first.')

        customer, _ = User.objects.get_or_create(
            email=QA_CUSTOMER_EMAIL,
            defaults={'full_name': 'QA Test Customer', 'role': 'buyer', 'is_verified': True,
                      'phone_number': '08000000001'},
        )
        vendor_user, _ = User.objects.get_or_create(
            email=QA_VENDOR_EMAIL,
            defaults={'full_name': 'QA Test Vendor', 'role': 'vendor', 'is_verified': True,
                      'phone_number': '08000000002'},
        )
        for user in (customer, vendor_user):
            user.set_unusable_password()
            user.save(update_fields=['password'])

        vendor, _ = Vendor.objects.get_or_create(user=vendor_user, defaults={
            'name': f'{QA_TAG} Kitchen',
            'email': QA_VENDOR_EMAIL,
            'phone_number': '08000000002',
            'address': 'Admiralty Way, Lekki Phase 1, Lagos',
            'location_latitude': VENDOR_LOCATION[0],
            'location_longitude': VENDOR_LOCATION[1],
            # Hidden from customers: inactive and not approved.
            'is_active': False,
            'approval_status': 'pending',
        })
        menu, _ = VendorCategory.objects.get_or_create(vendor=vendor, name='QA menu')
        product, _ = Product.objects.get_or_create(
            vendor=vendor, name=f'{QA_TAG} Jollof rice & chicken',
            defaults={'price': Decimal('3500'), 'category': menu, 'stock': 100, 'is_active': False},
        )

        now = timezone.now()
        created = []

        def make_order(status, delivery_status, drop, *, delivered_at=None, picked_up=None):
            address, lat, lon = drop
            order = Order.objects.create(
                user=customer,
                vendor=vendor,
                rider=rider,
                status=status,
                delivery_status=delivery_status,
                payment_status='paid',
                address=f'{QA_TAG} {address}, Lagos',
                location_latitude=lat,
                location_longitude=lon,
                delivery_latitude=lat,
                delivery_longitude=lon,
                total_amount=Decimal('7000'),
                delivery_fee=Decimal('1500'),
                note=f'{QA_TAG} test order, safe to complete',
                delivered_at=delivered_at,
                actual_delivery_time=delivered_at,
                actual_pickup_time=picked_up,
            )
            OrderItem.objects.create(order=order, product=product, quantity=2, price=Decimal('3500'))
            order.ensure_total_distance()
            created.append(order)
            return order

        # 8 delivered earlier this week (Monday onwards, never in the future).
        week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        for i in range(8):
            moment = max(
                timezone.make_aware(
                    timezone.datetime.combine(week_start, timezone.datetime.min.time())
                ) + timedelta(hours=9 + i),
                now - timedelta(hours=20 - i),
            )
            moment = min(moment, now - timedelta(minutes=30))
            make_order('delivered', 'delivered', DROP_OFFS[i % len(DROP_OFFS)],
                       delivered_at=moment, picked_up=moment - timedelta(minutes=25))

        waiting = make_order('rider_assigned', 'rider_assigned', DROP_OFFS[1])
        on_the_way = make_order('in_transit', 'in_transit', DROP_OFFS[2],
                                picked_up=now - timedelta(minutes=10))

        bonus = Decimal(str(options['bonus']))
        program = RiderRewardProgram.objects.create(
            name=f'{QA_TAG} Weekly 10 deliveries',
            description='Test reward: finish the two open test orders to earn it.',
            target_deliveries=10,
            bonus_amount=bonus,
            period='weekly',
            is_active=True,
            include_in_house_riders=True,
        )

        wallet, _ = Wallet.objects.get_or_create(user=rider.user)
        bank = {
            'bank_name': rider.user.bank_name or 'Access Bank',
            'account_number': rider.user.bank_account or '0123456789',
            'account_name': rider.user.bank_account_name or rider.user.full_name or 'Test Rider',
        }
        receipts = []
        for amount, status, hours in ((Decimal('15000'), 'completed', 30), (Decimal('12000'), 'pending', 2)):
            txn = WalletTransaction.objects.create(
                wallet=wallet,
                user=rider.user,
                amount=amount,
                transaction_type='withdrawal',
                status=status,
                description=f'{QA_TAG} Withdrawal from wallet',
                response_data={'data': {
                    'reason': f'Find My Taste withdrawal {QA_TAG}',
                    'recipient': {'details': bank},
                }},
            )
            WalletTransaction.objects.filter(pk=txn.pk).update(created_at=now - timedelta(hours=hours))
            receipts.append(txn)

        self.stdout.write(self.style.SUCCESS(
            f'Created test data for {rider.user.email} ({rider.user.full_name}).'))
        self.stdout.write(f'  Delivered this week: 8 orders (reward progress 8/10)')
        self.stdout.write(
            f'  Waiting for pickup: #{waiting.track_id}  delivery code {waiting.delivery_otp}'
            f'  ({waiting.total_distance} km)')
        self.stdout.write(
            f'  On the way:         #{on_the_way.track_id}  delivery code {on_the_way.delivery_otp}'
            f'  ({on_the_way.total_distance} km)')
        self.stdout.write(f'  Reward: "{program.name}" -> NGN {bonus} at 10 deliveries')
        self.stdout.write(f'  Withdrawal receipts: {", ".join(t.reference_code for t in receipts)}')
        self.stdout.write('  Remove everything with: python manage.py cleanup_rider_test_data '
                          f'--email {rider.user.email}')
