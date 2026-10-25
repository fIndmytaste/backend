"""Tests for the October 2026 feature batch: phone OTP, names, rider name
lock, admin accept-for-vendor, app versions, service fee, rewards, payouts,
transaction filters, receipts and order distance."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from account.models import Rider, User, Vendor, VerificationCode
from admin_manager.models import (
    AppVersionPolicy,
    EmailCampaign,
    RiderRewardAward,
    RiderRewardProgram,
)
from helpers.app_version import parse_version
from helpers.termii import normalize_nigerian_phone
from product.models import Order, SystemCategory
from wallet.models import Wallet, WalletTransaction
from wallet.receipts import build_withdrawal_receipt, mask_account_number, withdrawal_narration

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def make_vendor(email='vendor@example.com', **extra):
    category, _ = SystemCategory.objects.get_or_create(
        name_key='buka', defaults={'name': 'Buka', 'description': 'Food'})
    user = User.objects.create_user(email=email, password='pw', role='vendor', full_name='Vendor Owner')
    vendor = Vendor.objects.create(
        user=user, name='Test Kitchen', email=email, category=category,
        approval_status='approved', is_active=True,
        location_latitude='6.5244', location_longitude='3.3792', **extra)
    return vendor


class RegistrationNameTests(APITestCase):
    def test_three_part_names_are_accepted_and_tidied(self):
        res = self.client.post('/api/v1/auth/buyer-register/', {
            'full_name': '  Olanrewaju   Taiwo  Adebayo-Williams ',
            'phone_number': '08012345678',
            'email': 'three.names@example.com',
            'password': 'Passw0rd!',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        user = User.objects.get(email='three.names@example.com')
        self.assertEqual(user.full_name, 'Olanrewaju Taiwo Adebayo-Williams')

    def test_vendor_signup_accepts_long_full_name(self):
        res = self.client.post('/api/v1/auth/vendor-register/', {
            'full_name': 'Oluwaseun Temitope Adeyemi Babatunde',
            'phone_number': '08012345678',
            'email': 'long.vendor@example.com',
            'password': 'Passw0rd!',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)


@override_settings(CACHES=LOCMEM)
class PhoneVerificationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='phone@example.com', password='pw', role='buyer',
            full_name='Ada Obi', phone_number='08011111111', is_verified=True)
        self.client.force_authenticate(self.user)

    def test_normalize_phone(self):
        self.assertEqual(normalize_nigerian_phone('0801 234 5678'), '2348012345678')
        self.assertEqual(normalize_nigerian_phone('+234 801-234-5678'), '2348012345678')
        self.assertEqual(normalize_nigerian_phone('8012345678'), '2348012345678')
        self.assertIsNone(normalize_nigerian_phone('12345'))

    @patch('account.views.verification.send_sms', return_value='msg-1')
    def test_send_then_verify_marks_number_verified(self, send_sms):
        res = self.client.post('/api/v1/auth/phone/send-code/', {'phone_number': '08022222222'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        send_sms.assert_called_once()
        self.assertEqual(send_sms.call_args[0][0], '2348022222222')

        code = VerificationCode.objects.get(user=self.user, verification_type='phone').code
        self.assertEqual(len(code), 6)

        res = self.client.post('/api/v1/auth/phone/confirm-code/', {'code': code}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.phone_verified)
        self.assertEqual(self.user.phone_number, '08022222222')
        self.assertFalse(VerificationCode.objects.filter(user=self.user, verification_type='phone').exists())

    @patch('account.views.verification.send_sms', return_value='msg-1')
    def test_wrong_code_is_rejected_and_resend_is_throttled(self, send_sms):
        self.client.post('/api/v1/auth/phone/send-code/', {}, format='json')
        res = self.client.post('/api/v1/auth/phone/confirm-code/', {'code': '000000x'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/v1/auth/phone/send-code/', {}, format='json')
        self.assertEqual(res.status_code, 400)  # one per minute
        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)

    @patch('account.views.verification.send_sms')
    def test_sms_failure_returns_error_and_leaves_no_code(self, send_sms):
        from helpers.termii import TermiiError
        send_sms.side_effect = TermiiError('Could not send the SMS right now. Please try again.')
        res = self.client.post('/api/v1/auth/phone/send-code/', {}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(VerificationCode.objects.filter(user=self.user, verification_type='phone').exists())

    def test_changing_number_resets_verification(self):
        self.user.phone_verified = True
        self.user.save()
        res = self.client.patch('/api/v1/account/profile/', {'phone_number': '08099999999'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)

    def test_user_payload_exposes_phone_flags(self):
        from account.serializers import UserSerializer
        data = UserSerializer(self.user).data
        self.assertIn('phone_verified', data)
        self.assertIn('phone_verification_required', data)


class RiderNameLockTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='rider@example.com', password='pw', role='rider', full_name='Tunde Bello')
        self.rider = Rider.objects.create(user=self.user)
        self.client.force_authenticate(self.user)

    def _patch_name(self, name):
        from account.views.account import UserDetailView
        from rest_framework.test import APIRequestFactory, force_authenticate
        request = APIRequestFactory().patch('/', {'full_name': name}, format='json')
        force_authenticate(request, self.user)
        return UserDetailView.as_view()(request)

    def test_rider_cannot_rename_without_grant(self):
        res = self._patch_name('Someone Else')
        self.assertEqual(res.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, 'Tunde Bello')

    def test_grant_allows_exactly_one_rename(self):
        self.rider.name_change_allowed = True
        self.rider.save()
        self.assertEqual(self._patch_name('Tunde Ade Bello').status_code, 200)
        self.rider.refresh_from_db()
        self.assertFalse(self.rider.name_change_allowed)
        self.assertEqual(self._patch_name('Another Name').status_code, 403)

    def test_saving_same_name_is_not_blocked(self):
        self.assertEqual(self._patch_name('Tunde  Bello').status_code, 200)

    def test_admin_toggle(self):
        admin = User.objects.create_user(email='admin@example.com', password='pw', role='admin', is_staff=True)
        self.client.force_authenticate(admin)
        res = self.client.post(f'/api/v1/admin-manager/riders/{self.rider.id}/name-lock/', {'allowed': True}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.rider.refresh_from_db()
        self.assertTrue(self.rider.name_change_allowed)


class AdminAcceptForVendorTests(APITestCase):
    def setUp(self):
        self.vendor = make_vendor()
        self.customer = User.objects.create_user(email='c@example.com', password='pw', role='buyer', full_name='Cus Tomer')
        self.admin = User.objects.create_user(email='ops@example.com', password='pw', role='admin', is_staff=True)
        self.client.force_authenticate(self.admin)

    def _order(self, **kwargs):
        defaults = dict(user=self.customer, vendor=self.vendor, status='pending', payment_status='paid',
                        total_amount=Decimal('5000'))
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    @patch('vendor.views.send_new_order_push_notification_riders')
    @patch('vendor.views.send_order_accepted_notification_customer')
    def test_accepts_paid_pending_order(self, notify_customer, notify_riders):
        order = self._order()
        res = self.client.post(f'/api/v1/admin-manager/orders/{order.id}/accept-for-vendor/')
        self.assertEqual(res.status_code, 200, res.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'looking_for_rider')
        notify_customer.assert_called_once()
        notify_riders.assert_called_once()

    def test_rejects_unpaid_or_already_accepted(self):
        unpaid = self._order(payment_status='pending')
        res = self.client.post(f'/api/v1/admin-manager/orders/{unpaid.id}/accept-for-vendor/')
        self.assertEqual(res.status_code, 400)
        accepted = self._order(status='looking_for_rider')
        res = self.client.post(f'/api/v1/admin-manager/orders/{accepted.id}/accept-for-vendor/')
        self.assertEqual(res.status_code, 400)

    def test_customer_cannot_use_it(self):
        order = self._order()
        self.client.force_authenticate(self.customer)
        res = self.client.post(f'/api/v1/admin-manager/orders/{order.id}/accept-for-vendor/')
        self.assertEqual(res.status_code, 403)


class AppVersionTests(APITestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version('1.0.3+5'), (1, 0, 3, 0))
        self.assertLess(parse_version('1.0.9'), parse_version('1.0.10'))
        self.assertIsNone(parse_version('abc'))

    def test_check(self):
        AppVersionPolicy.objects.create(
            app='rider', platform='android', latest_version='1.2.0', minimum_version='1.1.0',
            store_url='https://play.google.com/store/apps/details?id=x')
        url = '/api/v1/app-version/check/?app=rider&platform=android&version='
        old = self.client.get(url + '1.0.5').data['data']
        self.assertTrue(old['update_available'])
        self.assertTrue(old['force_update'])
        mid = self.client.get(url + '1.1.2').data['data']
        self.assertTrue(mid['update_available'])
        self.assertFalse(mid['force_update'])
        new = self.client.get(url + '1.2.0').data['data']
        self.assertFalse(new['update_available'])

    def test_no_policy_never_forces(self):
        res = self.client.get('/api/v1/app-version/check/?app=customer&platform=ios&version=0.0.1')
        self.assertFalse(res.data['data']['force_update'])


@override_settings(CACHES=LOCMEM)
class ServiceFeeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_percentage_until_fixed_amount_is_saved(self):
        from helpers.models import DeliveryConfiguration
        from helpers.order_utils import DeliveryConfig

        # Legacy: 2.5% of 4000 = 100 (cap 500)
        self.assertAlmostEqual(DeliveryConfig.service_fee_for(4000), 100.0)
        DeliveryConfiguration.objects.create(
            key='service_fee_amount', category='pricing', data_type='float',
            value='150', default_value='0', description='Fixed service fee')
        cache.clear()
        self.assertAlmostEqual(DeliveryConfig.service_fee_for(4000), 150.0)
        self.assertAlmostEqual(DeliveryConfig.service_fee_for(100000), 150.0)
        self.assertEqual(DeliveryConfig.service_fee_for(0), 0.0)


class RiderRewardTests(TestCase):
    def setUp(self):
        self.vendor = make_vendor()
        self.customer = User.objects.create_user(email='cust@example.com', password='pw', role='buyer')
        self.rider_user = User.objects.create_user(email='r@example.com', password='pw', role='rider', full_name='Rider One')
        self.rider = Rider.objects.create(user=self.rider_user)
        self.program = RiderRewardProgram.objects.create(
            name='Weekly 3', target_deliveries=3, bonus_amount=Decimal('2000'),
            period='weekly', is_active=True)

    def _deliver(self, n):
        for _ in range(n):
            Order.objects.create(
                user=self.customer, vendor=self.vendor, rider=self.rider,
                status='delivered', delivery_status='delivered', payment_status='paid',
                delivered_at=timezone.now(), total_amount=Decimal('1000'))

    def test_bonus_paid_once_when_target_met(self):
        from admin_manager.rewards import evaluate_rider_rewards, rider_reward_progress

        self._deliver(2)
        self.assertEqual(evaluate_rider_rewards(), 0)
        self.assertEqual(rider_reward_progress(self.rider)[0]['remaining_deliveries'], 1)

        self._deliver(1)
        self.assertEqual(evaluate_rider_rewards(), 1)
        self.assertEqual(evaluate_rider_rewards(), 0)  # never twice

        wallet = Wallet.objects.get(user=self.rider_user)
        self.assertEqual(wallet.balance, Decimal('2000.00'))
        self.assertEqual(RiderRewardAward.objects.count(), 1)
        txn = WalletTransaction.objects.get(user=self.rider_user, transaction_type='reward')
        self.assertEqual(txn.status, 'completed')
        self.assertTrue(rider_reward_progress(self.rider)[0]['earned'])

    def test_inactive_program_pays_nothing(self):
        from admin_manager.rewards import evaluate_rider_rewards
        self.program.is_active = False
        self.program.save()
        self._deliver(5)
        self.assertEqual(evaluate_rider_rewards(), 0)


class VendorAutoPayoutTests(APITestCase):
    def setUp(self):
        self.vendor = make_vendor(bank_account='0123456789', bank_name='Access Bank', bank_account_name='Test Kitchen')
        self.client.force_authenticate(self.vendor.user)

    def test_vendor_request_then_admin_enables(self):
        res = self.client.post('/api/v1/vendor/auto-payout/', {'enabled': True}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.vendor.refresh_from_db()
        self.assertTrue(self.vendor.auto_payout_requested)
        self.assertFalse(self.vendor.auto_payout_enabled)

        admin = User.objects.create_user(email='a@example.com', password='pw', role='admin', is_staff=True)
        self.client.force_authenticate(admin)
        listed = self.client.get('/api/v1/admin-manager/auto-payout-requests/').data['data']
        self.assertEqual(len(listed), 1)
        res = self.client.post(f'/api/v1/admin-manager/vendor/{self.vendor.id}/auto-payout/', {'enabled': True}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.vendor.refresh_from_db()
        self.assertTrue(self.vendor.auto_payout_enabled)
        self.assertFalse(self.vendor.auto_payout_requested)

    @patch('helpers.paystack.PaystackManager.initiate_transfer', return_value=(True, 'ok'))
    def test_task_pays_cleared_balance_above_minimum(self, transfer):
        from wallet.tasks import process_vendor_auto_payouts
        self.vendor.auto_payout_enabled = True
        self.vendor.save()
        wallet = Wallet.objects.get(user=self.vendor.user)
        wallet.balance = Decimal('50000')
        wallet.save()
        summary = process_vendor_auto_payouts()
        self.assertEqual(summary['paid'], [str(self.vendor.id)])
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('0.00'))
        self.assertEqual(transfer.call_args.kwargs['reason'], 'automatic payout')

    @patch('helpers.paystack.PaystackManager.initiate_transfer', return_value=(True, 'ok'))
    def test_task_skips_balance_below_minimum(self, transfer):
        from wallet.tasks import process_vendor_auto_payouts
        self.vendor.auto_payout_enabled = True
        self.vendor.save()
        wallet = Wallet.objects.get(user=self.vendor.user)
        wallet.balance = Decimal('100')
        wallet.save()
        process_vendor_auto_payouts()
        transfer.assert_not_called()


class TransactionFilterTests(APITestCase):
    def test_filter_by_user_type_and_type(self):
        rider = User.objects.create_user(email='tr@example.com', password='pw', role='rider')
        buyer = User.objects.create_user(email='tb@example.com', password='pw', role='buyer')
        for user, kind in ((rider, 'withdrawal'), (buyer, 'deposit'), (rider, 'earning')):
            WalletTransaction.objects.create(
                wallet=Wallet.objects.get(user=user), user=user, amount=100,
                transaction_type=kind, status='completed')
        admin = User.objects.create_user(email='ta@example.com', password='pw', role='admin', is_staff=True)
        self.client.force_authenticate(admin)

        def count(query):
            res = self.client.get(f'/api/v1/admin-manager/transactions/?{query}')
            self.assertEqual(res.status_code, 200)
            return res.data['metadata']['count']

        self.assertEqual(count('user_type=rider'), 2)
        self.assertEqual(count('user_type=customer'), 1)
        self.assertEqual(count('user_type=rider&transaction_type=withdrawal'), 1)


class ReceiptTests(TestCase):
    def test_withdrawal_receipt_and_narration(self):
        user = User.objects.create_user(
            email='rcpt@example.com', password='pw', role='rider', full_name='Kemi Ade',
            bank_account='0123456789', bank_name='GTBank', bank_account_name='KEMI ADE')
        txn = WalletTransaction.objects.create(
            wallet=Wallet.objects.get(user=user), user=user, amount=Decimal('15000'),
            transaction_type='withdrawal', status='completed', description='Withdrawal from wallet')
        narration = withdrawal_narration(txn, 'Withdrawal from balance')
        self.assertEqual(narration, f'Find My Taste rider withdrawal NGN 15,000.00 ref {txn.reference_code}')

        receipt = build_withdrawal_receipt(txn)
        self.assertEqual(receipt['bank_name'], 'GTBank')
        self.assertEqual(receipt['account_number_masked'], mask_account_number('0123456789'))
        self.assertTrue(receipt['account_number_masked'].endswith('6789'))
        self.assertEqual(receipt['recipient_name'], 'Kemi Ade')
        self.assertTrue(receipt['narration'].startswith(
            'Withdrawal of NGN 15,000.00 from your Find My Taste rider wallet to KEMI ADE, GTBank '))
        self.assertIn('6789 on ', receipt['narration'])
        self.assertTrue(receipt['narration'].endswith(f'Ref {txn.reference_code}.'))
        self.assertTrue(receipt['bank_narration'].startswith('Find My Taste rider withdrawal'))

    def test_non_withdrawals_have_no_receipt(self):
        user = User.objects.create_user(email='rc2@example.com', password='pw', role='rider')
        txn = WalletTransaction.objects.create(
            wallet=Wallet.objects.get(user=user), user=user, amount=1, transaction_type='earning')
        self.assertIsNone(build_withdrawal_receipt(txn))


class OrderDistanceTests(TestCase):
    def test_distance_computed_and_saved(self):
        vendor = make_vendor()
        customer = User.objects.create_user(email='d@example.com', password='pw', role='buyer')
        order = Order.objects.create(
            user=customer, vendor=vendor, status='pending',
            location_latitude=Decimal('6.4550'), location_longitude=Decimal('3.3941'))
        km = order.ensure_total_distance()
        self.assertTrue(7 < km < 9, km)  # Lagos Island to Yaba-ish, ~7.9 km
        order.refresh_from_db()
        self.assertAlmostEqual(float(order.total_distance), km, places=2)

    def test_missing_coordinates_return_none(self):
        vendor = make_vendor(email='v2@example.com')
        customer = User.objects.create_user(email='d2@example.com', password='pw', role='buyer')
        order = Order.objects.create(user=customer, vendor=vendor, status='pending')
        self.assertIsNone(order.ensure_total_distance())


class CampaignTests(TestCase):
    def test_audience_respects_opt_out_and_role(self):
        User.objects.create_user(email='in@example.com', password='pw', role='buyer')
        User.objects.create_user(email='out@example.com', password='pw', role='buyer', marketing_emails_opt_in=False)
        User.objects.create_user(email='rid@example.com', password='pw', role='rider')
        campaign = EmailCampaign.objects.create(subject='Hi', body='Hello', audience='customers')
        emails = set(campaign.recipients().values_list('email', flat=True))
        self.assertEqual(emails, {'in@example.com'})

    def test_send_and_unsubscribe(self):
        from django.core import mail
        from admin_manager.campaigns import send_campaign, unsubscribe_url_for

        user = User.objects.create_user(email='promo@example.com', password='pw', role='buyer', full_name='Promo User')
        campaign = EmailCampaign.objects.create(
            subject='Weekend deals', body='Para one.\n\nPara two.', audience='customers',
            status='sending', cta_label='Order now', cta_url='https://findmytaste.com.ng')
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            send_campaign(campaign.id)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sent')
        self.assertEqual(campaign.sent_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('List-Unsubscribe', mail.outbox[0].extra_headers)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Hi Promo', html)
        self.assertIn('cid:findmytaste-logo', html)

        path = unsubscribe_url_for(user).split('/api/v1')[1]
        res = self.client.get('/api/v1' + path)
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.marketing_emails_opt_in)


class EmailBrandingTests(TestCase):
    """Logo embedded in every email, and admin links that actually open."""

    def _sent_message(self, send):
        from django.core import mail
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            send()
        self.assertEqual(len(mail.outbox), 1)
        return mail.outbox[0].message()

    def _inline_logo(self, message):
        parts = [p for p in message.walk() if p.get('Content-ID') == '<findmytaste-logo>']
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_content_type(), 'image/png')
        self.assertTrue(parts[0].get_payload(decode=True).startswith(b'\x89PNG'))

    def test_campaign_embeds_logo_and_links_body_addresses(self):
        from admin_manager.campaigns import send_campaign_email

        campaign = EmailCampaign(
            subject='Deals', audience='all',
            body='See https://findmytaste.com.ng/deals?a=1&b=2 or www.example.com today.\n\n<b>not html</b>',
            cta_label='Order now', cta_url='https://findmytaste.com.ng/order')
        message = self._sent_message(lambda: send_campaign_email(campaign, 'a@example.com', name='Ada'))
        self.assertEqual(message.get_content_type(), 'multipart/related')
        self._inline_logo(message)
        html = next(p for p in message.walk() if p.get_content_type() == 'text/html').get_payload(decode=True).decode()
        self.assertIn('src="cid:findmytaste-logo"', html)
        self.assertIn('href="https://findmytaste.com.ng/deals?a=1&amp;b=2"', html)
        self.assertIn('href="https://www.example.com"', html)
        self.assertIn('href="https://findmytaste.com.ng/order"', html)
        self.assertIn('&lt;b&gt;not html&lt;/b&gt;', html)
        self.assertIn('Find My Taste <support@findmytaste.com.ng>', message['From'])

    def test_campaigns_can_use_their_own_mail_server(self):
        from admin_manager.campaigns import campaign_connection

        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('CAMPAIGN_EMAIL_HOST', None)
            self.assertIsNone(campaign_connection())
        with patch.dict('os.environ', {
                'CAMPAIGN_EMAIL_HOST': 'smtp.zoho.com', 'CAMPAIGN_EMAIL_PORT': '465',
                'CAMPAIGN_EMAIL_USER': 'support@findmytaste.com.ng', 'CAMPAIGN_EMAIL_PASSWORD': 'x'}):
            connection = campaign_connection()
        self.assertEqual(connection.host, 'smtp.zoho.com')
        self.assertTrue(connection.use_ssl)
        self.assertFalse(connection.use_tls)

    def test_button_link_without_https_is_saved_with_it(self):
        from admin_manager.views.growth import EmailCampaignSerializer

        ok = EmailCampaignSerializer(data={
            'subject': 'S', 'body': 'B', 'cta_label': 'Go', 'cta_url': 'findmytaste.com.ng/promo'})
        self.assertTrue(ok.is_valid(), ok.errors)
        self.assertEqual(ok.validated_data['cta_url'], 'https://findmytaste.com.ng/promo')
        bad = EmailCampaignSerializer(data={
            'subject': 'S', 'body': 'B', 'cta_label': 'Go', 'cta_url': 'not a link'})
        self.assertFalse(bad.is_valid())

    def test_transactional_emails_embed_logo(self):
        from helpers.email import EmailService

        message = self._sent_message(lambda: EmailService().send_email_with_template(
            'b@example.com', 'emails/account_activation.html',
            {'user_name': 'Bola', 'verification_code': '123456', 'expiry_time': '24 hours'},
            'Verify', async_send=False))
        self._inline_logo(message)
        self.assertIn('Find My Taste <support@findmytaste.com.ng>', message['From'])


@override_settings(CACHES=LOCMEM)
class GoogleSignInTests(APITestCase):
    def _info(self, **extra):
        info = {'aud': 'web-client.apps.googleusercontent.com', 'email': 'NewPerson@Gmail.com',
                'email_verified': True, 'name': 'New Person Okafor', 'picture': 'https://x/p.png'}
        info.update(extra)
        return info

    @patch.dict('os.environ', {'GOOGLE_OAUTH_CLIENT_IDS': 'web-client.apps.googleusercontent.com'})
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_creates_customer_and_returns_tokens(self, verify):
        verify.return_value = self._info()
        res = self.client.post('/api/v1/auth/google/', {'id_token': 't'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['data']['is_new_user'])
        self.assertTrue(res.data['data']['needs_phone'])
        self.assertIn('access', res.data['data']['tokens'])
        user = User.objects.get(email='newperson@gmail.com')
        self.assertEqual(user.role, 'buyer')
        self.assertEqual(user.auth_provider, 'google')
        self.assertTrue(user.is_verified)
        self.assertFalse(user.has_usable_password())

    @patch.dict('os.environ', {'GOOGLE_OAUTH_CLIENT_IDS': 'web-client.apps.googleusercontent.com'})
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_existing_account_signs_in(self, verify):
        existing = User.objects.create_user(email='newperson@gmail.com', password='pw', role='buyer')
        verify.return_value = self._info()
        res = self.client.post('/api/v1/auth/google/', {'id_token': 't'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['data']['is_new_user'])
        self.assertEqual(res.data['data']['user']['id'], str(existing.id))

    @patch.dict('os.environ', {'GOOGLE_OAUTH_CLIENT_IDS': 'web-client.apps.googleusercontent.com'})
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_rejects_other_audience_and_unverified_email(self, verify):
        verify.return_value = self._info(aud='someone-else')
        self.assertEqual(self.client.post('/api/v1/auth/google/', {'id_token': 't'}, format='json').status_code, 400)
        verify.return_value = self._info(email_verified=False)
        self.assertEqual(self.client.post('/api/v1/auth/google/', {'id_token': 't'}, format='json').status_code, 400)
        self.assertFalse(User.objects.filter(email='newperson@gmail.com').exists())

    @patch.dict('os.environ', {'GOOGLE_OAUTH_CLIENT_IDS': ''})
    def test_disabled_without_client_ids(self):
        res = self.client.post('/api/v1/auth/google/', {'id_token': 't'}, format='json')
        self.assertEqual(res.status_code, 400)


@override_settings(CACHES=LOCMEM)
@patch.dict('os.environ', {'PHONE_VERIFICATION_REQUIRED': 'true', 'TERMII_API_KEY': 'test-key'})
class SmsInsteadOfEmailTests(APITestCase):
    @patch('account.views.verification.send_sms', return_value='m1')
    def test_signup_code_goes_by_sms_and_verifies_phone(self, send_sms):
        res = self.client.post('/api/v1/auth/vendor-register/', {
            'full_name': 'Sms Vendor', 'phone_number': '0803 333 4444',
            'email': 'smsvendor@example.com', 'password': 'Passw0rd!',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['data']['otp_channel'], 'sms')
        self.assertEqual(send_sms.call_args[0][0], '2348033334444')

        user = User.objects.get(email='smsvendor@example.com')
        code = VerificationCode.objects.get(user=user, verification_type='email').code
        self.assertIn(code, send_sms.call_args[0][1])
        res = self.client.post('/api/v1/auth/verify/', {'email': user.email, 'code': code}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        user.refresh_from_db()
        self.assertTrue(user.phone_verified)
        self.assertEqual(user.phone_number, '08033334444')

    @patch('account.views.verification.send_sms', return_value='m1')
    def test_login_uses_sms_only_for_verified_numbers(self, send_sms):
        user = User.objects.create_user(
            email='login@example.com', password='pw', role='buyer',
            phone_number='08055556666', is_verified=True)
        res = self.client.post('/api/v1/auth/login/', {'email': user.email, 'password': 'pw'}, format='json')
        self.assertEqual(res.data['data']['otp_channel'], 'email')
        send_sms.assert_not_called()

        user.phone_verified = True
        user.save()
        res = self.client.post('/api/v1/auth/login/', {'email': user.email, 'password': 'pw'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['data']['otp_channel'], 'sms')
        code = VerificationCode.objects.filter(user=user, verification_type='login').last().code
        res = self.client.post('/api/v1/auth/verify-login/', {'email': user.email, 'code': code}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

    @patch('account.views.verification.send_sms')
    def test_sms_failure_falls_back_to_email(self, send_sms):
        from helpers.termii import TermiiError
        send_sms.side_effect = TermiiError('down')
        res = self.client.post('/api/v1/auth/buyer-register/', {
            'full_name': 'Fall Back', 'phone_number': '08077778888',
            'email': 'fallback@example.com', 'password': 'Passw0rd!',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['data']['otp_channel'], 'email')

    @patch.dict('os.environ', {'PHONE_VERIFICATION_REQUIRED': 'false'})
    @patch('account.views.verification.send_sms')
    def test_flag_off_keeps_email(self, send_sms):
        User.objects.create_user(email='off@example.com', password='pw', role='buyer',
                                 phone_number='08011112222', is_verified=True, phone_verified=True)
        res = self.client.post('/api/v1/auth/login/', {'email': 'off@example.com', 'password': 'pw'}, format='json')
        self.assertEqual(res.data['data']['otp_channel'], 'email')
        send_sms.assert_not_called()


class PhoneValidationTests(APITestCase):
    def _register(self, phone):
        return self.client.post('/api/v1/auth/buyer-register/', {
            'full_name': 'Phone Person', 'phone_number': phone,
            'email': f'p{abs(hash(phone))}@example.com', 'password': 'Passw0rd!',
        }, format='json')

    def test_invalid_numbers_are_rejected(self):
        for bad in ['12345', '0601234567', 'abc', '08012']:
            self.assertEqual(self._register(bad).status_code, 400, bad)

    def test_valid_numbers_are_stored_in_local_format(self):
        res = self._register('+234 803 333 4444')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(User.objects.filter(phone_number='08033334444').exists())

    def test_profile_update_validates_phone(self):
        user = User.objects.create_user(email='pv@example.com', password='pw', role='buyer')
        self.client.force_authenticate(user)
        res = self.client.patch('/api/v1/account/profile/', {'phone_number': '123'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.patch('/api/v1/account/profile/', {'phone_number': '0905 111 2222'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        user.refresh_from_db()
        self.assertEqual(user.phone_number, '09051112222')


@override_settings(CACHES=LOCMEM)
class AppleSignInTests(APITestCase):
    @patch('account.views.verification.verify_apple_identity_token')
    def test_new_apple_user_needs_phone_and_returning_user_matched_by_sub(self, verify):
        verify.return_value = {'sub': 'apple-123', 'email': 'relay@privaterelay.appleid.com',
                               'email_verified': 'true'}
        res = self.client.post('/api/v1/auth/apple/', {'identity_token': 't', 'full_name': 'Ada Obi'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['data']['is_new_user'])
        self.assertTrue(res.data['data']['needs_phone'])
        user = User.objects.get(apple_sub='apple-123')
        self.assertEqual(user.full_name, 'Ada Obi')
        self.assertEqual(user.auth_provider, 'apple')

        # Later sign-ins carry no email; the Apple id still finds the account.
        verify.return_value = {'sub': 'apple-123'}
        res = self.client.post('/api/v1/auth/apple/', {'identity_token': 't'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['data']['is_new_user'])
        self.assertEqual(res.data['data']['user']['id'], str(user.id))

    @patch('account.views.verification.verify_apple_identity_token')
    def test_unverified_email_never_takes_over_existing_account(self, verify):
        User.objects.create_user(email='owner@example.com', password='pw', role='buyer')
        verify.return_value = {'sub': 'apple-9', 'email': 'owner@example.com', 'email_verified': 'false'}
        res = self.client.post('/api/v1/auth/apple/', {'identity_token': 't'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.filter(apple_sub='apple-9').exists())

    @patch('account.views.verification.verify_apple_identity_token')
    def test_bad_token_rejected(self, verify):
        verify.side_effect = Exception('bad signature')
        res = self.client.post('/api/v1/auth/apple/', {'identity_token': 't'}, format='json')
        self.assertEqual(res.status_code, 400)


class PhoneVerificationNeedsTermiiTests(APITestCase):
    @patch.dict('os.environ', {'PHONE_VERIFICATION_REQUIRED': 'true', 'TERMII_API_KEY': ''})
    def test_flag_without_termii_requires_nothing(self):
        from account.serializers import UserSerializer
        user = User.objects.create_user(email='nt@example.com', password='pw', role='vendor')
        data = UserSerializer(user).data
        self.assertFalse(data['phone_verification_required'])
        self.assertFalse(data['sms_verification_available'])


class RiderTestDataCommandTests(TestCase):
    def test_seed_reward_and_cleanup(self):
        from io import StringIO
        from django.core.management import call_command
        from admin_manager.rewards import evaluate_rider_rewards, rider_reward_progress

        user = User.objects.create_user(email='Akakurup@yahoo.com', password='pw', role='rider', full_name='Pascal A')
        rider = Rider.objects.create(user=user)
        real = WalletTransaction.objects.create(
            wallet=Wallet.objects.get(user=user), user=user, amount=500,
            transaction_type='earning', status='completed', description='Real earning')

        out = StringIO()
        call_command('seed_rider_test_data', '--email', 'akakurup@yahoo.com', stdout=out)
        self.assertIn('delivery code', out.getvalue())
        self.assertEqual(Order.objects.filter(rider=rider).count(), 10)
        self.assertTrue(all(o.total_distance for o in Order.objects.filter(rider=rider)))
        progress = rider_reward_progress(rider)
        self.assertEqual(progress[0]['completed_deliveries'], 8)
        # QA vendor is never visible to customers.
        self.assertFalse(Vendor.objects.get(user__email='qa-vendor@qa-test.findmytaste.ng').is_active)

        # Finish the two open orders -> bonus is paid.
        for order in Order.objects.filter(rider=rider).exclude(status='delivered'):
            order.status = 'delivered'
            order.delivered_at = timezone.now()
            order.save()
        self.assertEqual(evaluate_rider_rewards(), 1)
        self.assertEqual(Wallet.objects.get(user=user).balance, Decimal('2000.00'))

        # Running twice is refused.
        with self.assertRaises(Exception):
            call_command('seed_rider_test_data', '--email', 'akakurup@yahoo.com', stdout=StringIO())

        call_command('cleanup_rider_test_data', '--email', 'akakurup@yahoo.com', stdout=StringIO())
        self.assertEqual(Order.objects.filter(rider=rider).count(), 0)
        self.assertFalse(RiderRewardProgram.objects.exists())
        self.assertFalse(User.objects.filter(email__endswith='qa-test.findmytaste.ng').exists())
        self.assertEqual(Wallet.objects.get(user=user).balance, Decimal('0.00'))
        # The rider's real data is untouched.
        self.assertTrue(WalletTransaction.objects.filter(pk=real.pk).exists())
        self.assertTrue(Rider.objects.filter(pk=rider.pk).exists())
        self.assertEqual(WalletTransaction.objects.filter(user=user).count(), 1)


@override_settings(CACHES=LOCMEM)
class DeliveryFromEstimateTests(TestCase):
    def test_clean_rising_prices_and_times(self):
        from helpers.order_utils import DeliveryConfig, estimate_delivery_from
        cache.clear()
        near = estimate_delivery_from(0.8)
        mid = estimate_delivery_from(4.0)
        far = estimate_delivery_from(9.0)
        for est in (near, mid, far):
            self.assertEqual(est['fee'] % 100, 0)
            self.assertGreaterEqual(est['fee'], DeliveryConfig.MIN_DELIVERY_FEE // 100 * 100)
            self.assertEqual(est['minutes'] % 5, 0)
        self.assertLessEqual(near['fee'], mid['fee'])
        self.assertLess(mid['fee'], far['fee'])
        self.assertLess(near['minutes'], far['minutes'])

    def test_vendor_card_shows_from_price_not_zero(self):
        from vendor.serializers import BuyerVendorCardSerializer
        vendor = make_vendor(email='card@example.com')
        vendor.distance_km = 3.2
        data = BuyerVendorCardSerializer(vendor).data
        self.assertGreater(float(data['starting_delivery_price']), 0)
        self.assertNotEqual(data['estimated_delivery_time'], '0:30:00')
