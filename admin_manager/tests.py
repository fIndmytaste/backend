from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from account.models import Rider, User, Vendor
from product.models import (
    BukaItemServiceCharge,
    BukaVariantServiceCharge,
    Order,
    OrderItem,
    OrderItemVariant,
    PlatformSettings,
    Product,
    ProductVariant,
    ProductVariantCategory,
    SystemCategory,
)
from vendor.models import MarketPlace
from wallet.models import PaystackFeeRecord, Wallet, WalletTransaction


class AdminDashboardOverviewTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='overview-admin@example.com',
            password='password',
        )
        self.customer = User.objects.create_user(
            email='overview-customer@example.com',
            password='password',
        )
        self.category = SystemCategory.objects.create(
            name='Buka',
            name_key='buka',
            description='Food vendors',
        )
        vendor_user = User.objects.create_user(
            email='overview-vendor@example.com',
            password='password',
            role='vendor',
        )
        self.vendor = Vendor.objects.create(
            user=vendor_user,
            name='Independent Vendor',
            email=vendor_user.email,
            category=self.category,
            approval_status='approved',
            is_active=True,
        )
        marketplace_vendor_user = User.objects.create_user(
            email='overview-marketplace-vendor@example.com',
            password='password',
            role='vendor',
        )
        self.marketplace_vendor = Vendor.objects.create(
            user=marketplace_vendor_user,
            name='Marketplace Vendor',
            email=marketplace_vendor_user.email,
            category=self.category,
            approval_status='approved',
            is_active=True,
            is_marketplace=True,
        )
        self.marketplace = MarketPlace.objects.create(name='Main Marketplace')
        self.marketplace.vendors.add(self.marketplace_vendor)

        rider_user = User.objects.create_user(
            email='overview-rider@example.com',
            password='password',
            role='rider',
        )
        self.rider = Rider.objects.create(
            user=rider_user,
            mode_of_transport='bike',
            is_in_house_rider=False,
        )
        in_house_rider_user = User.objects.create_user(
            email='overview-marketplace-rider@example.com',
            password='password',
            role='rider',
        )
        self.in_house_rider = Rider.objects.create(
            user=in_house_rider_user,
            mode_of_transport='bike',
            is_in_house_rider=True,
        )
        settings = PlatformSettings.get_settings()
        settings.rider_commission_percentage = 10
        settings.save()
        self.client.force_authenticate(self.admin)

    def create_order(self, **overrides):
        values = {
            'user': self.customer,
            'vendor': self.vendor,
            'rider': self.rider,
            'payment_status': 'paid',
            'status': 'delivered',
            'delivery_status': 'delivered',
            'total_amount': 1000,
            'vendor_amount': 700,
            'delivery_fee': 1000,
            'rider_earning': 900,
            'rider_gross_earning': 1000,
            'rider_commission_amount': 100,
            'rider_commission_percentage_applied': 10,
            'platform_marketplace_delivery_amount': 0,
            'platform_amount': 300,
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def test_revenue_summary_breaks_down_all_platform_income(self):
        vendor_order = self.create_order()
        marketplace_order = self.create_order(
            vendor=self.marketplace_vendor,
            rider=self.in_house_rider,
            vendor_amount=800,
            delivery_fee=400,
            rider_earning=0,
            rider_gross_earning=0,
            rider_commission_amount=0,
            rider_commission_percentage_applied=0,
            platform_marketplace_delivery_amount=400,
            platform_amount=50,
        )
        self.create_order(
            status='in_transit',
            delivery_status='in_transit',
            rider_earning=999,
            rider_gross_earning=None,
            rider_commission_amount=None,
            rider_commission_percentage_applied=None,
            platform_amount=25,
        )
        self.create_order(
            payment_status='pending',
            rider_earning=500,
            platform_amount=500,
        )
        vendor_wallet = Wallet.objects.get(user=self.vendor.user)
        marketplace_wallet = Wallet.objects.get(user=self.marketplace_vendor.user)
        rider_wallet = Wallet.objects.get(user=self.rider.user)
        WalletTransaction.objects.create(
            wallet=vendor_wallet,
            user=self.vendor.user,
            order=vendor_order,
            amount=700,
            transaction_type='earning',
            status='completed',
        )
        WalletTransaction.objects.create(
            wallet=marketplace_wallet,
            user=self.marketplace_vendor.user,
            order=marketplace_order,
            amount=800,
            transaction_type='earning',
            status='completed',
        )
        WalletTransaction.objects.create(
            wallet=rider_wallet,
            user=self.rider.user,
            order=vendor_order,
            amount=900,
            transaction_type='earning',
            status='completed',
        )

        response = self.client.get(
            reverse('dashboard-overview'),
            {'period': 'week'},
        )

        self.assertEqual(response.status_code, 200)
        summary = response.data['data']['revenue_summary']
        platform = summary['platform_earnings']
        self.assertEqual(summary['vendor_payouts']['value'], 1500.0)
        self.assertEqual(summary['rider_payouts']['value'], 900.0)
        self.assertEqual(summary['vendor_balance_credits']['value'], 1500.0)
        self.assertEqual(summary['rider_balance_credits']['value'], 900.0)
        self.assertEqual(summary['completed_vendor_payouts']['value'], 0.0)
        self.assertEqual(summary['completed_rider_payouts']['value'], 0.0)
        self.assertEqual(
            summary['earned_but_not_necessarily_paid']['riders']['value'],
            900.0,
        )
        self.assertEqual(
            platform['breakdown']['vendor_service_charges']['value'],
            375.0,
        )
        self.assertEqual(
            platform['breakdown']['rider_commissions']['value'],
            100.0,
        )
        self.assertEqual(
            platform['breakdown']['marketplace_delivery_fees']['value'],
            400.0,
        )
        self.assertEqual(platform['value'], 875.0)

    def test_balance_credit_totals_are_independent_of_paystack_withdrawals(self):
        vendor_wallet = Wallet.objects.get(user=self.vendor.user)
        rider_wallet = Wallet.objects.get(user=self.rider.user)
        WalletTransaction.objects.create(
            wallet=vendor_wallet,
            user=self.vendor.user,
            amount=700,
            transaction_type='withdrawal',
            status='completed',
        )
        WalletTransaction.objects.create(
            wallet=rider_wallet,
            user=self.rider.user,
            amount=900,
            transaction_type='withdrawal',
            status='completed',
        )
        WalletTransaction.objects.create(
            wallet=rider_wallet,
            user=self.rider.user,
            amount=250,
            transaction_type='withdrawal',
            status='pending',
        )

        response = self.client.get(reverse('dashboard-overview'), {'period': 'week'})

        summary = response.data['data']['revenue_summary']
        self.assertEqual(summary['vendor_payouts']['value'], 0.0)
        self.assertEqual(summary['rider_payouts']['value'], 0.0)
        self.assertEqual(summary['completed_vendor_payouts']['value'], 700.0)
        self.assertEqual(summary['completed_rider_payouts']['value'], 900.0)
        self.assertEqual(summary['withdrawal_count']['value'], 2)
        self.assertEqual(summary['withdrawal_count']['breakdown']['vendors']['value'], 1)
        self.assertEqual(summary['withdrawal_count']['breakdown']['riders']['value'], 1)
        self.assertEqual(summary['pending_payouts']['value'], 250.0)
        self.assertEqual(
            summary['pending_payouts']['breakdown']['riders']['value'], 250.0)

    def test_paystack_summary_includes_payout_principal_and_total_debit(self):
        PaystackFeeRecord.objects.create(
            direction='payout',
            reference='overview-payout',
            gross_amount=1000,
            fee_amount=25,
            net_amount=1025,
            paid_at=timezone.now(),
        )

        response = self.client.get(reverse('dashboard-overview'), {'period': 'week'})

        paystack = response.data['data']['revenue_summary']['paystack_fees']
        self.assertEqual(paystack['breakdown']['payout_fees']['value'], 25.0)
        self.assertEqual(paystack['gross_paid_out']['value'], 1000.0)
        self.assertEqual(paystack['total_debited_for_payouts']['value'], 1025.0)

    def test_revenue_summary_derives_legacy_financial_snapshots(self):
        self.create_order(
            rider_gross_earning=None,
            rider_commission_amount=None,
            rider_commission_percentage_applied=None,
        )
        self.create_order(
            vendor=self.marketplace_vendor,
            rider=self.in_house_rider,
            delivery_fee=400,
            rider_earning=0,
            rider_gross_earning=None,
            rider_commission_amount=None,
            rider_commission_percentage_applied=None,
            platform_marketplace_delivery_amount=None,
            platform_amount=50,
        )

        response = self.client.get(reverse('dashboard-overview'), {'period': 'week'})

        platform = response.data['data']['revenue_summary']['platform_earnings']
        self.assertEqual(
            platform['breakdown']['rider_commissions']['value'],
            100.0,
        )
        self.assertEqual(
            platform['breakdown']['marketplace_delivery_fees']['value'],
            400.0,
        )

    def test_product_and_variant_service_charges_feed_platform_amount(self):
        product = Product.objects.create(
            name='Rice Bowl',
            description='Rice',
            price=1000,
            vendor=self.vendor,
            system_category=self.category,
        )
        BukaItemServiceCharge.objects.create(
            vendor=self.vendor,
            product=product,
            flat_charge=100,
        )
        variant_category = ProductVariantCategory.objects.create(
            category_name='Protein',
            parent_product=product,
        )
        variant = ProductVariant.objects.create(
            category=variant_category,
            product=product,
            name='Chicken',
            price=200,
        )
        BukaVariantServiceCharge.objects.create(
            vendor=self.vendor,
            product=product,
            variant=variant,
            flat_charge=50,
        )
        order = self.create_order(
            total_amount=1350,
            vendor_amount=0,
            platform_amount=0,
        )
        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=product.get_price_with_commission(),
        )
        OrderItemVariant.objects.create(
            order_item=order_item,
            variant=variant,
            quantity=1,
            price_at_purchase=variant.get_price_with_commission(),
        )

        order.save_vendor_and_commision(gross_order_amount=1350)
        order.refresh_from_db()

        self.assertEqual(float(order.vendor_amount), 1200.0)
        self.assertEqual(float(order.platform_amount), 150.0)

        # Delivery must use the purchase-time settlement even if catalog
        # prices change before the order is completed.
        product.price = 5000
        product.save(update_fields=['price'])
        variant.price = 1000
        variant.save(update_fields=['price'])
        order.credit_vendor_earning_once()
        order.refresh_from_db()

        self.assertEqual(float(order.vendor_amount), 1200.0)
        self.assertEqual(float(order.platform_amount), 150.0)
