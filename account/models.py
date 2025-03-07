import random
import uuid
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models



class UserManager(BaseUserManager):
    """
    Custom manager for the User model.
    """

    def create_user(self, email, password, **extra_fields):
        """
        Create a regular user with the given email and password.
        """
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_admin', True)



        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must be given is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must be given is_superuser=True')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=64, null=True, blank=True)
    first_name = models.CharField(max_length=64, null=True, blank=True)
    last_name = models.CharField(max_length=64, null=True, blank=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20,null=True,blank=True)
    is_verified = models.BooleanField(default=False, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email



class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    country = models.CharField(max_length=64)
    state = models.CharField(max_length=64, null=True,blank=True)
    city = models.CharField(max_length=64, null=True,blank=True)
    address = models.TextField(null=True,blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, null=True,blank=True)
    address = models.CharField(max_length=256)
    description = models.TextField(null=True, blank=True)
    logo = models.ImageField(upload_to='vendor_image', null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey('product.SystemCategory' , on_delete=models.SET_NULL, null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    open_time = models.TimeField(auto_now=True)
    close_time = models.TimeField(auto_now=True)
    bank_account = models.CharField(max_length=20,null=True,blank=True)
    bank_name = models.CharField(max_length=64,null=True,blank=True)
    bank_account_name = models.CharField(max_length=64,null=True,blank=True)
    open_day = models.CharField(
        max_length=10,
        choices=[
            ('Monday', 'Monday'),
            ('Tuesday', 'Tuesday'),
            ('Wednesday', 'Wednesday'),
            ('Thursday', 'Thursday'),
            ('Friday', 'Friday'),
            ('Saturday', 'Saturday'),
            ('Sunday', 'Sunday'),
        ],
        default='Monday'
    )
    close_day = models.CharField(
        max_length=10,
        choices=[
            ('Monday', 'Monday'),
            ('Tuesday', 'Tuesday'),
            ('Wednesday', 'Wednesday'),
            ('Thursday', 'Thursday'),
            ('Friday', 'Friday'),
            ('Saturday', 'Saturday'),
            ('Sunday', 'Sunday'),
        ],
        default='Monday'
    )





class VendorRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.DecimalField(max_digits=3, decimal_places=2)  # e.g., 4.5 out of 5
    comment = models.TextField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vendor', 'user')  # Ensure each user can rate a vendor only once

    def __str__(self):
        return f"Rating for {self.vendor.name} by {self.user.email}"



class VerificationCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6, unique=True)
    verification_type = models.CharField(
        max_length=32,
        choices=[
            ('email', 'Email Verification'),
            ('phone', 'Phone Verification'),
            ('password', 'Password Reset'),
        ]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



    @classmethod
    def generate_unique_six_digit_code(cls):
        """Generate a unique six-digit verification code."""
        while True:
            code = str(random.randint(100000, 999999))  
            if not cls.objects.filter(code=code).exists(): 
                return code

    def save(self, *args, **kwargs):
        """Override save method to generate code before saving."""
        if not self.code:
            self.code = VerificationCode.generate_unique_six_digit_code()
        super().save(*args, **kwargs)  # Call the original save method

    def __str__(self):
        return f"VerificationCode for {self.user.username} ({self.verification_type})"




class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    content = models.TextField(null=True,blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)