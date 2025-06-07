import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()  
# Create your models here.





class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Store balance
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"Wallet for {self.user.username}"

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(choices=TRANSACTION_TYPES, max_length=10)
    status = models.CharField(choices=TRANSACTION_STATUS, max_length=10, default='pending')  # New field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} for {self.wallet.user.username} - {self.status}"
