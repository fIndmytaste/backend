import uuid
from django.db import models
from django.contrib.auth import get_user_model

from product.models import Order

User = get_user_model()
# Create your models here.


class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)  # Store balance
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.user.email}"

    def deposit(self, amount):
        """
        Adds funds to the user's wallet.
        """
        if amount <= 0:
            raise ValueError("Amount to deposit must be positive")
        self.balance += amount
        self.save()

    def withdraw(self, amount):
        """
        Deducts funds from the user's wallet.
        """
        if self.balance >= amount:
            self.balance -= amount
            self.save()
        else:
            raise ValueError("Insufficient funds in wallet")

    def get_balance(self):
        """
        Returns the current balance of the wallet.
        """
        return self.balance


# serving as the general transaction table
class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('purchase', 'Purchase'),
        ('earning', 'Rider Earning')
    ]

    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed')
    ]

    TRANSACTION_PREFIXES = {
        'deposit': 'DEP',
        'withdrawal': 'WTD',
        'purchase': 'PAY',
        'earning': 'ERN',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="transactions")
    user = models.ForeignKey(
        User,  on_delete=models.SET_NULL, null=True, blank=True,)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(
        choices=TRANSACTION_TYPES, max_length=10)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(
        choices=TRANSACTION_STATUS, max_length=10, default='pending')  # New field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    external_reference = models.TextField(null=True, blank=True)
    response_data = models.JSONField(null=True, blank=True)
    reference_code = models.CharField(
        max_length=50, unique=True, editable=False, null=True, blank=True)
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True)

    @staticmethod
    def generate_reference_code(prefix):
        random_part = uuid.uuid4().hex[:20].upper()
        return f"{prefix}-{random_part}"

    def __str__(self):
        user_email = self.wallet.user.email if self.wallet_id and self.wallet else "no-wallet"
        return f"{self.transaction_type} of {self.amount} for {user_email} - {self.status}"

    def save(self, *args, **kwargs):
        if not self.reference_code:
            prefix = self.TRANSACTION_PREFIXES.get(
                self.transaction_type, 'TXN')
            self.reference_code = WalletTransaction.generate_reference_code(
                prefix)
        super().save(*args, **kwargs)


class PaystackFeeRecord(models.Model):
    """
    One row per Paystack money movement, holding the fee Paystack charged us.

    Every naira that enters or leaves the platform through Paystack passes a
    toll: collections (card / bank transfer / dedicated account) are settled to
    us net of a processing fee, and payouts (vendor & rider withdrawals) are
    debited with a transfer fee. Neither shows up in `Order` or
    `WalletTransaction`, so platform revenue read off those tables is gross —
    it overstates what actually lands in the bank.

    This table is the missing ledger. It is written from Paystack's own
    payloads (webhook / verify response), so `fee_amount` is what Paystack
    reported, not what we guessed. When a payload carries no fee — Paystack's
    transfer objects usually don't — we fall back to the published fee schedule
    and flag the row `is_estimated=True` so the dashboard can say how much of
    the total is reported vs. estimated, and the balance-ledger sync can
    correct it later.
    """

    COLLECTION = 'collection'
    PAYOUT = 'payout'
    REVERSAL = 'reversal'
    DIRECTION_CHOICES = [
        (COLLECTION, 'Collection (money in)'),
        (PAYOUT, 'Payout (money out)'),
        (REVERSAL, 'Reversal (money returned)'),
    ]

    SOURCE_CHOICES = [
        ('webhook', 'Paystack webhook'),
        ('verify', 'Paystack verify API'),
        ('balance_ledger', 'Paystack balance ledger'),
        ('backfill', 'Backfilled from stored payload'),
        ('estimate', 'Estimated from fee schedule'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    direction = models.CharField(
        max_length=16, choices=DIRECTION_CHOICES, default=COLLECTION,
        help_text="Whether this movement brought money in or took money out.")
    wallet_transaction = models.ForeignKey(
        WalletTransaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paystack_fees',
        help_text="The platform transaction this Paystack movement settles.")
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paystack_fees',
        help_text="The order paid for, when this is an order collection.")
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paystack_fees',
        help_text="The customer who paid, or the recipient who was paid out.")

    reference = models.CharField(
        max_length=255, db_index=True,
        help_text="Paystack reference for the charge/transfer.")
    paystack_id = models.CharField(
        max_length=64, null=True, blank=True,
        help_text="Paystack's own numeric id for the transaction/transfer.")
    channel = models.CharField(
        max_length=64, null=True, blank=True,
        help_text="card, bank_transfer, dedicated_nuban, transfer, ...")
    currency = models.CharField(max_length=8, default='NGN')

    gross_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text="Amount that moved, in naira, before Paystack's fee.")
    fee_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text="What Paystack charged on this movement, in naira.")
    net_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text="Settled to us (collection) or total debited (payout).")

    is_estimated = models.BooleanField(
        default=False,
        help_text="True when the fee came from our schedule, not from Paystack.")
    source = models.CharField(
        max_length=32, choices=SOURCE_CHOICES, default='webhook',
        help_text="Where this row's numbers came from.")
    paid_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="When Paystack processed the movement.")
    raw_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One row per Paystack movement. Re-delivered webhooks and a verify
        # call landing after the webhook must update, never duplicate.
        constraints = [
            models.UniqueConstraint(
                fields=['direction', 'reference'],
                name='unique_paystack_fee_per_reference',
            )
        ]
        indexes = [
            models.Index(fields=['direction', 'paid_at']),
        ]
        ordering = ['-paid_at', '-created_at']

    def __str__(self):
        return f"{self.direction} {self.reference}: fee {self.fee_amount} {self.currency}"
