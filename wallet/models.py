import uuid
from django.db import models
from django.contrib.auth import get_user_model

from product.models import Order

User = get_user_model()  
# Create your models here.





class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Store balance
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



class WalletTransaction(models.Model): # serving as the general transaction table
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('purchase', 'Purchase')
    ]

    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]

    TRANSACTION_PREFIXES = {
        'deposit': 'DEP',
        'withdrawal': 'WTD',
        'purchase': 'PAY',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(choices=TRANSACTION_TYPES, max_length=10)
    description = models.TextField(null=True,blank=True)
    status = models.CharField(choices=TRANSACTION_STATUS, max_length=10, default='pending')  # New field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reference_code = models.CharField(max_length=50, unique=True, editable=False, null=True, blank=True)
    order = models.ForeignKey(Order,on_delete=models.SET_NULL,null=True,blank=True)

    @staticmethod
    def generate_reference_code(prefix):
        random_part = uuid.uuid4().hex[:20].upper()
        return f"{prefix}-{random_part}"

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} for {self.wallet.user.email} - {self.status}"

    def save(self, *args, **kwargs):
        if not self.reference_code:
            prefix = self.TRANSACTION_PREFIXES.get(self.transaction_type, 'TXN')
            self.reference_code = WalletTransaction.generate_reference_code(prefix)
        super().save(*args, **kwargs)