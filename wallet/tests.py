from unittest.mock import patch

from django.test import TestCase

from account.models import User
from helpers.paystack import PaystackManager
from helpers.paystack_fees import import_payouts_from_transfers_api
from wallet.models import PaystackFeeRecord, Wallet, WalletTransaction


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
