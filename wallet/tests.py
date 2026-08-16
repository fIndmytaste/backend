from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from account.models import User, Vendor
from helpers.paystack import PaystackManager
from helpers.paystack_fees import import_payouts_from_transfers_api
from product.models import Order, SystemCategory
from wallet.models import PaystackFeeRecord, Wallet, WalletTransaction
from wallet.settlement import (
    SETTLEMENT_HOLD_HOURS,
    held_amount,
    next_clearance_at,
    withdrawable_balance,
)


class PaystackTransferReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='paystack-rider@example.com',
            password='password',
            role='rider',
        )
        self.wallet = Wallet.objects.get(user=self.user)
        self.withdrawal = WalletTransaction.objects.create(
            wallet=self.wallet,
            user=self.user,
            amount=1000,
            transaction_type='withdrawal',
            status='pending',
        )

    @patch('helpers.paystack.PaystackManager.list_transfers')
    def test_successful_transfer_completes_withdrawal_and_records_reported_fee(
        self, list_transfers
    ):
        list_transfers.return_value = (True, [{
            'id': 12345,
            'reference': str(self.withdrawal.id),
            'amount': 100000,
            'fee_charged': 1000,
            'currency': 'NGN',
            'status': 'success',
            'updatedAt': '2026-08-11T10:00:00.000Z',
        }])

        stats = import_payouts_from_transfers_api()

        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, 'completed')
        self.assertEqual(self.withdrawal.external_reference, str(self.withdrawal.id))
        fee = PaystackFeeRecord.objects.get(
            direction='payout', reference=str(self.withdrawal.id))
        self.assertEqual(float(fee.gross_amount), 1000.0)
        self.assertEqual(float(fee.fee_amount), 10.0)
        self.assertFalse(fee.is_estimated)
        self.assertEqual(stats['completed_withdrawals'], 1)

    @patch('helpers.paystack.PaystackManager.list_transfers')
    def test_non_successful_transfer_remains_pending(self, list_transfers):
        list_transfers.return_value = (True, [{
            'reference': str(self.withdrawal.id),
            'amount': 100000,
            'status': 'pending',
        }])

        stats = import_payouts_from_transfers_api()

        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, 'pending')
        self.assertEqual(stats['recorded'], 0)
        self.assertFalse(PaystackFeeRecord.objects.exists())

    @patch('helpers.paystack.requests.post')
    def test_instant_success_is_completed_and_fee_is_recorded(self, post):
        self.user.bank_name = '044'
        self.user.bank_account = '0123456789'
        self.user.bank_account_name = 'Test Rider'
        self.user.save()

        class Response:
            ok = True
            status_code = 200

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        post.side_effect = [
            Response({'data': {'recipient_code': 'RCP_test'}}),
            Response({'status': True, 'data': {
                'id': 999,
                'reference': str(self.withdrawal.id),
                'amount': 100000,
                'fee_charged': 1000,
                'currency': 'NGN',
                'status': 'success',
            }}),
        ]
        manager = PaystackManager()

        with patch.object(manager, 'resolve_bank_identifier', return_value='044'), \
             patch.object(manager, 'resolve_bank_account', return_value=(True, {
                 'account_number': '0123456789',
                 'account_name': 'Test Rider',
             })):
            success, _message = manager.initiate_transfer(
                user=self.user,
                vendor=None,
                amount=self.withdrawal.amount,
                transaction_obj=self.withdrawal,
            )

        self.assertTrue(success)
        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, 'completed')
        self.assertTrue(PaystackFeeRecord.objects.filter(
            direction='payout', reference=str(self.withdrawal.id)).exists())


class VendorSettlementHoldTests(APITestCase):
    """
    Paystack settles a collection ~24h after the customer pays, so a vendor
    earning can sit in the wallet balance while still being unspendable. These
    cover the line between the two.
    """

    def setUp(self):
        self.category = SystemCategory.objects.create(
            name='Buka',
            name_key='buka',
            description='Food vendors',
        )
        self.vendor_user = User.objects.create_user(
            email='hold-vendor@example.com',
            password='password',
            role='vendor',
        )
        self.vendor_user.bank_account = '0123456789'
        self.vendor_user.save()
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            name='Hold Vendor',
            email=self.vendor_user.email,
            category=self.category,
            approval_status='approved',
            is_active=True,
        )
        self.customer = User.objects.create_user(
            email='hold-customer@example.com',
            password='password',
        )
        self.wallet = Wallet.objects.get(user=self.vendor_user)

    def create_earning(self, amount, order_age_hours, user=None, wallet=None):
        """An earning credited for an order placed `order_age_hours` ago."""
        order = Order.objects.create(
            user=self.customer,
            vendor=self.vendor,
            payment_status='paid',
            status='delivered',
            delivery_status='delivered',
            total_amount=amount,
            vendor_amount=amount,
        )
        placed_at = timezone.now() - timedelta(hours=order_age_hours)
        Order.objects.filter(pk=order.pk).update(created_at=placed_at)

        wallet = self.wallet if wallet is None else wallet
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            user=self.vendor_user if user is None else user,
            order=order,
            amount=amount,
            transaction_type='earning',
            status='completed',
        )
        wallet.deposit(Decimal(str(amount)))
        return transaction

    def test_earning_from_an_old_order_is_fully_withdrawable(self):
        self.create_earning(5000, order_age_hours=48)
        self.wallet.refresh_from_db()

        self.assertEqual(held_amount(self.vendor_user), Decimal('0.00'))
        self.assertEqual(withdrawable_balance(self.wallet), Decimal('5000.00'))

    def test_earning_from_a_fresh_order_is_held_but_still_in_the_balance(self):
        self.create_earning(5000, order_age_hours=1)
        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal('5000.00'))
        self.assertEqual(held_amount(self.vendor_user), Decimal('5000.00'))
        self.assertEqual(withdrawable_balance(self.wallet), Decimal('0.00'))

    def test_only_the_cleared_part_of_a_mixed_balance_is_withdrawable(self):
        self.create_earning(8000, order_age_hours=48)
        self.create_earning(3000, order_age_hours=2)
        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal('11000.00'))
        self.assertEqual(withdrawable_balance(self.wallet), Decimal('8000.00'))

    def test_an_order_exactly_past_the_window_has_cleared(self):
        self.create_earning(5000, order_age_hours=SETTLEMENT_HOLD_HOURS + 1)
        self.wallet.refresh_from_db()

        self.assertEqual(withdrawable_balance(self.wallet), Decimal('5000.00'))

    def test_legacy_earning_rows_without_a_user_are_still_held(self):
        # Historical rows carry only `wallet`; missing them would let held
        # money be withdrawn.
        self.create_earning(4000, order_age_hours=1)
        WalletTransaction.objects.filter(wallet=self.wallet).update(user=None)
        self.wallet.refresh_from_db()

        self.assertEqual(held_amount(self.vendor_user), Decimal('4000.00'))
        self.assertEqual(withdrawable_balance(self.wallet), Decimal('0.00'))

    def test_next_clearance_is_24h_after_the_oldest_held_order(self):
        self.create_earning(3000, order_age_hours=2)
        self.create_earning(3000, order_age_hours=10)

        clears_at = next_clearance_at(self.vendor_user)
        expected = timezone.now() + timedelta(hours=SETTLEMENT_HOLD_HOURS - 10)
        self.assertIsNotNone(clears_at)
        self.assertLess(abs((clears_at - expected).total_seconds()), 60)

    def test_riders_are_not_subject_to_the_vendor_hold(self):
        rider_user = User.objects.create_user(
            email='hold-rider@example.com',
            password='password',
            role='rider',
        )
        rider_wallet = Wallet.objects.get(user=rider_user)
        WalletTransaction.objects.create(
            wallet=rider_wallet,
            user=rider_user,
            amount=5000,
            transaction_type='earning',
            status='completed',
        )
        rider_wallet.deposit(Decimal('5000'))

        self.assertEqual(held_amount(rider_user), Decimal('0.00'))
        self.assertEqual(withdrawable_balance(rider_wallet), Decimal('5000.00'))

    def test_withdrawal_of_uncleared_money_is_rejected(self):
        self.create_earning(100000, order_age_hours=1)
        self.client.force_authenticate(self.vendor_user)

        response = self.client.post(
            '/api/v1/wallet/withdraw/', {'amount': '50000'}, format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.wallet.refresh_from_db()
        # The balance must be untouched — no funds held against a rejected request.
        self.assertEqual(self.wallet.balance, Decimal('100000.00'))
        self.assertFalse(
            WalletTransaction.objects.filter(transaction_type='withdrawal').exists()
        )

    def test_balance_payload_reports_the_cleared_split(self):
        self.create_earning(8000, order_age_hours=48)
        self.create_earning(3000, order_age_hours=2)
        self.client.force_authenticate(self.vendor_user)

        response = self.client.get('/api/v1/wallet/balance/')

        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertEqual(data['balance'], '11000.00')
        self.assertEqual(data['available_balance'], '8000.00')
        self.assertEqual(data['pending_clearance'], '3000.00')
        self.assertEqual(data['clearance_hold_hours'], SETTLEMENT_HOLD_HOURS)
