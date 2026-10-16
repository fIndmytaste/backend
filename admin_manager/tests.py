from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from account.models import (
    Rider,
    StaffMarketplaceAssignment,
    StaffPagePermission,
    User,
    Vendor,
)
from product.models import (
    BukaItemServiceCharge,
    BukaVariantServiceCharge,
    Order,
    DeclinedOrder,
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


class MarketplaceStaffOrderVisibilityTests(APITestCase):
    """
    Marketplace staff work a 24-hour-delayed view of the order book, because
    an order younger than that has not settled at Paystack yet. Superusers are
    never delayed.
    """

    def setUp(self):
        self.category = SystemCategory.objects.create(
            name='Buka',
            name_key='buka',
            description='Food vendors',
        )
        self.customer = User.objects.create_user(
            email='visibility-customer@example.com',
            password='password',
        )
        vendor_user = User.objects.create_user(
            email='visibility-vendor@example.com',
            password='password',
            role='vendor',
        )
        self.vendor = Vendor.objects.create(
            user=vendor_user,
            name='Marketplace Vendor',
            email=vendor_user.email,
            category=self.category,
            approval_status='approved',
            is_active=True,
            is_marketplace=True,
        )
        self.marketplace = MarketPlace.objects.create(name='Mile 12')
        self.marketplace.vendors.add(self.vendor)

        self.staff = User.objects.create_user(
            email='visibility-staff@example.com',
            password='password',
        )
        self.staff.is_staff = True
        self.staff.save()
        StaffPagePermission.objects.create(user=self.staff, page='marketplace-staff')
        StaffMarketplaceAssignment.objects.create(
            user=self.staff, marketplace=self.marketplace,
        )

        self.superadmin = User.objects.create_superuser(
            email='visibility-admin@example.com',
            password='password',
        )

        self.old_order = self.create_order(age_hours=30)
        self.fresh_order = self.create_order(age_hours=2)

    def create_order(self, age_hours):
        order = Order.objects.create(
            user=self.customer,
            vendor=self.vendor,
            payment_status='paid',
            status='pending',
            total_amount=1000,
            vendor_amount=700,
            platform_amount=300,
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=age_hours),
        )
        return order

    def listed_order_ids(self):
        response = self.client.get(reverse('admin-marketplace-vendors-all-orders'))
        self.assertEqual(response.status_code, 200)
        return {str(order['id']) for order in response.data['results']}

    def test_staff_only_see_orders_older_than_the_settlement_window(self):
        self.client.force_authenticate(self.staff)

        listed = self.listed_order_ids()

        self.assertIn(str(self.old_order.id), listed)
        self.assertNotIn(str(self.fresh_order.id), listed)

    def test_superadmin_sees_every_order_immediately(self):
        self.client.force_authenticate(self.superadmin)

        listed = self.listed_order_ids()

        self.assertIn(str(self.old_order.id), listed)
        self.assertIn(str(self.fresh_order.id), listed)

    def test_staff_still_see_the_real_placement_time_of_a_visible_order(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(reverse('admin-marketplace-vendors-all-orders'))
        listed = {str(order['id']): order for order in response.data['results']}

        self.assertIsNotNone(listed[str(self.old_order.id)]['created_at'])

    def test_staff_cannot_open_an_order_inside_the_window_directly(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(
            reverse('admin-order-detail', kwargs={'id': self.fresh_order.id}),
        )

        self.assertIn(response.status_code, (400, 404))

    def test_staff_can_open_an_order_past_the_window(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(
            reverse('admin-order-detail', kwargs={'id': self.old_order.id}),
        )

        self.assertEqual(response.status_code, 200)


class AdminReleaseRiderAssignmentTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='release-admin@example.com', password='password',
        )
        self.customer = User.objects.create_user(
            email='release-customer@example.com', password='password',
        )
        category = SystemCategory.objects.create(
            name='Release test food', name_key='release-test-food',
        )
        vendor_user = User.objects.create_user(
            email='release-vendor@example.com', password='password', role='vendor',
        )
        self.vendor = Vendor.objects.create(
            user=vendor_user,
            name='Release Test Vendor',
            email=vendor_user.email,
            category=category,
            approval_status='approved',
            is_active=True,
        )
        rider_user = User.objects.create_user(
            email='release-rider@example.com', password='password', role='rider',
        )
        self.rider = Rider.objects.create(
            user=rider_user,
            mode_of_transport='bike',
            status='active',
            is_verified=True,
        )
        self.order = Order.objects.create(
            user=self.customer,
            vendor=self.vendor,
            rider=self.rider,
            payment_status='paid',
            status='rider_assigned',
            delivery_status='rider_assigned',
            total_amount=1000,
        )
        self.client.force_authenticate(self.admin)

    @patch('admin_manager.views.products.notify_order_available_to_riders')
    @patch('admin_manager.views.products.notify_rider_assignment_released')
    def test_release_returns_order_to_public_rider_pool(
        self, released_notification, available_notification,
    ):
        DeclinedOrder.objects.create(rider=self.rider, order=self.order)

        response = self.client.post(
            reverse('admin-release-rider-assignment', kwargs={'id': self.order.id}),
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.rider)
        self.assertEqual(self.order.status, 'looking_for_rider')
        self.assertEqual(self.order.delivery_status, 'awaiting_rider')
        self.assertFalse(self.order.declined_by_riders.exists())
        self.assertEqual(response.data['data']['availability'], 'rider_pool')
        released_notification.assert_called_once()
        available_notification.assert_called_once()

    def test_release_is_blocked_after_pickup(self):
        self.order.status = 'picked_up'
        self.order.delivery_status = 'picked_up'
        self.order.actual_pickup_time = timezone.now()
        self.order.save()

        response = self.client.post(
            reverse('admin-release-rider-assignment', kwargs={'id': self.order.id}),
        )

        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.rider, self.rider)

    def test_awaiting_pickup_filter_only_lists_releasable_assignments(self):
        picked_up = Order.objects.create(
            user=self.customer,
            vendor=self.vendor,
            rider=self.rider,
            payment_status='paid',
            status='picked_up',
            delivery_status='picked_up',
            actual_pickup_time=timezone.now(),
            total_amount=1000,
        )

        response = self.client.get(
            reverse('admin-orders-list'),
            {'assignment_status': 'awaiting_pickup'},
        )

        self.assertEqual(response.status_code, 200)
        ids = {str(item['id']) for item in response.data['results']}
        self.assertIn(str(self.order.id), ids)
        self.assertNotIn(str(picked_up.id), ids)


class AdminVendorCatalogueTests(APITestCase):
    """Admins managing a vendor's products on the vendor's behalf."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='catalogue-admin@example.com', password='password',
        )
        self.category = SystemCategory.objects.create(
            name='Catalogue food', name_key='catalogue-food',
        )
        self.vendor = self._make_vendor('catalogue-vendor@example.com', 'Catalogue Vendor')
        self.other_vendor = self._make_vendor('catalogue-other@example.com', 'Other Vendor')
        self.client.force_authenticate(self.admin)

        upload_patch = patch(
            'vendor.views.upload_to_backblaze',
            side_effect=lambda **kw: {'downloadUrl': f"https://f.backblazeb2.com/{kw['file_name']}"},
        )
        self.upload = upload_patch.start()
        self.addCleanup(upload_patch.stop)

    def _make_vendor(self, email, name):
        user = User.objects.create_user(email=email, password='password', role='vendor')
        return Vendor.objects.create(
            user=user, name=name, email=email, category=self.category,
            approval_status='approved', is_active=True,
        )

    def _image(self, name='dish.png'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(name, b'\x89PNG\r\n\x1a\n', content_type='image/png')

    def _variants_json(self, **overrides):
        import json
        group = {
            'variant_category_name': 'Size',
            'select_at_least_one_variant': True,
            'allow_multiple_quantity': False,
            'allow_multiple_variant_selection': False,
            'max_quantity_per_variant': None,
            'variants': [
                {'name': 'Small', 'price': 1500, 'stock': 0},
                {'name': 'Large', 'price': 2500, 'stock': 5},
            ],
        }
        group.update(overrides)
        return json.dumps([group])

    def _create_url(self, vendor=None):
        return reverse('admin-vendor-product-create', kwargs={'vendor_id': (vendor or self.vendor).id})

    def _detail_url(self, product, vendor=None):
        return reverse('admin-vendor-product-detail', kwargs={
            'vendor_id': (vendor or self.vendor).id, 'product_id': product.id,
        })

    def _create_product(self, **extra):
        data = {
            'name': 'Jollof rice', 'description': 'Smoky party jollof', 'price': '2000',
            'stock': '0', 'is_active': 'true', 'product_variant': self._variants_json(),
            'images': [self._image('a.png'), self._image('b.png')],
        }
        data.update(extra)
        return self.client.post(self._create_url(), data, format='multipart')

    def test_admin_creates_product_with_variants_images_and_menu_category(self):
        from product.models import ProductImage, VendorCategory
        menu = VendorCategory.objects.create(vendor=self.vendor, name='Rice', description='')

        response = self._create_product(category=str(menu.id), system_category=str(self.category.id))

        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(id=response.data['data']['id'])
        self.assertEqual(product.vendor, self.vendor)
        self.assertEqual(product.category, menu)
        self.assertEqual(product.system_category, self.category)
        group = ProductVariantCategory.objects.get(parent_product=product)
        self.assertEqual(group.category_name, 'Size')
        self.assertTrue(group.select_at_least_one_variant_enabled)
        self.assertEqual(
            sorted(ProductVariant.objects.filter(category=group).values_list('name', flat=True)),
            ['Large', 'Small'],
        )
        images = ProductImage.objects.filter(product=product)
        self.assertEqual(images.count(), 2)
        self.assertEqual(images.filter(is_primary=True).count(), 1)
        # Admin sees the vendor's own price, not the customer price.
        self.assertEqual(response.data['data']['price'], 2000.0)

    def test_admin_bypasses_product_creation_lock_without_using_a_grant(self):
        self.vendor.product_creation_locked = True
        self.vendor.product_creation_grant_count = 1
        self.vendor.save()

        response = self._create_product()

        self.assertEqual(response.status_code, 201, response.data)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.product_creation_grant_count, 1)

    def test_menu_category_from_another_vendor_is_rejected(self):
        from product.models import VendorCategory
        foreign = VendorCategory.objects.create(vendor=self.other_vendor, name='Soups', description='')

        response = self._create_product(category=str(foreign.id))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.objects.filter(vendor=self.vendor).exists())

    def test_staff_needs_vendor_page_permission(self):
        staff = User.objects.create_user(
            email='catalogue-staff@example.com', password='password', is_staff=True,
        )
        self.client.force_authenticate(staff)
        self.assertEqual(self._create_product().status_code, 403)

        StaffPagePermission.objects.create(user=staff, page='vendor')
        self.assertEqual(self._create_product().status_code, 201)

    def test_customer_cannot_create_products_for_vendors(self):
        customer = User.objects.create_user(email='catalogue-customer@example.com', password='password')
        self.client.force_authenticate(customer)
        self.assertEqual(self._create_product().status_code, 403)

    def test_admin_edits_product_and_replaces_variants(self):
        product = Product.objects.get(id=self._create_product().data['data']['id'])
        variants = self._variants_json(variants=[{'name': 'Medium', 'price': 1800, 'stock': 0}])

        response = self.client.patch(
            self._detail_url(product),
            {'name': 'Jollof special', 'is_active': 'false', 'product_variant': variants},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.name, 'Jollof special')
        self.assertFalse(product.is_active)
        active = ProductVariant.objects.filter(product=product, is_active=True)
        self.assertEqual(list(active.values_list('name', flat=True)), ['Medium'])

    def test_product_of_another_vendor_is_not_found(self):
        product = Product.objects.get(id=self._create_product().data['data']['id'])
        response = self.client.get(self._detail_url(product, vendor=self.other_vendor))
        self.assertEqual(response.status_code, 404)

    def test_admin_deletes_product(self):
        product = Product.objects.get(id=self._create_product().data['data']['id'])
        response = self.client.delete(self._detail_url(product))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(id=product.id).exists())

    def test_deleting_primary_image_promotes_another(self):
        from product.models import ProductImage
        product = Product.objects.get(id=self._create_product().data['data']['id'])
        primary = ProductImage.objects.get(product=product, is_primary=True)

        response = self.client.delete(reverse('admin-vendor-product-image-delete', kwargs={
            'vendor_id': self.vendor.id, 'product_id': product.id, 'image_id': primary.id,
        }))

        self.assertEqual(response.status_code, 200)
        remaining = ProductImage.objects.filter(product=product)
        self.assertEqual(remaining.count(), 1)
        self.assertTrue(remaining.get().is_primary)

    def test_menu_categories_are_created_once_and_listed_per_vendor(self):
        url = reverse('admin-vendor-categories', kwargs={'vendor_id': self.vendor.id})

        first = self.client.post(url, {'name': 'Rice dishes'})
        again = self.client.post(url, {'name': 'rice dishes'})
        listed = self.client.get(url)
        other = self.client.get(reverse('admin-vendor-categories', kwargs={'vendor_id': self.other_vendor.id}))

        self.assertEqual(first.status_code, 201)
        self.assertEqual(again.data['data']['id'], first.data['data']['id'])
        self.assertEqual([c['name'] for c in listed.data['data']], ['Rice dishes'])
        self.assertEqual(other.data['data'], [])


class AdminBulkAssignMarketplaceOrdersTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='bulk-admin@example.com', password='password',
        )
        category = SystemCategory.objects.create(name='Bulk market', name_key='bulk-market')
        vendor_user = User.objects.create_user(
            email='bulk-vendor@example.com', password='password', role='vendor',
        )
        self.vendor = Vendor.objects.create(
            user=vendor_user, name='Bulk Market Stall', email=vendor_user.email,
            category=category, approval_status='approved', is_active=True,
            is_marketplace=True,
        )
        rider_user = User.objects.create_user(
            email='bulk-rider@example.com', password='password', role='rider',
        )
        self.rider = Rider.objects.create(
            user=rider_user, mode_of_transport='bike', status='active',
            is_verified=True, is_in_house_rider=True,
        )
        customer = User.objects.create_user(email='bulk-customer@example.com', password='password')
        self.orders = [
            Order.objects.create(
                user=customer, vendor=self.vendor, payment_status='paid',
                status='looking_for_rider', total_amount=1000,
            )
            for _ in range(2)
        ]
        self.client.force_authenticate(self.admin)

    def test_assigns_every_marketplace_order_to_the_rider(self):
        response = self.client.post(
            reverse('admin_bulk_assign_marketplace_orders'),
            {'rider_id': str(self.rider.id), 'order_ids': [str(o.id) for o in self.orders]},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        for order in self.orders:
            order.refresh_from_db()
            self.assertEqual(order.rider, self.rider)
            self.assertEqual(order.status, 'rider_assigned')
