import random
import uuid
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from cloudinary.models import CloudinaryField
from datetime import timedelta



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
        extra_fields.setdefault('role', 'admin')



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
    profile_image = CloudinaryField('profile_images', null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20,null=True,blank=True)
    is_verified = models.BooleanField(default=False, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bank_account = models.CharField(max_length=20,null=True,blank=True)
    bank_name = models.CharField(max_length=64,null=True,blank=True)
    bank_account_name = models.CharField(max_length=64,null=True,blank=True)

    role = models.CharField(max_length=10, choices=(
        ('admin', 'Admin'),
        ('buyer','buyer'),
        ('vendor','vendor'),
        ('rider','rider'),
    ), default='buyer')

    objects = UserManager()
    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email


    def get_profile_image(self):
        print(self.get_profile_image)
        try:
            return self.profile_image.url
        except:
            return None



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
    location_latitude = models.CharField(max_length=20, null=True, blank=True)
    location_longitude = models.CharField(max_length=20, null=True, blank=True)
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
    country = models.CharField(max_length=64,null=True,blank=True)
    state = models.CharField(max_length=64, null=True,blank=True)
    city = models.CharField(max_length=64, null=True,blank=True)
    address = models.CharField(max_length=256)
    location_latitude = models.CharField(max_length=20, null=True, blank=True)
    location_longitude = models.CharField(max_length=20, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    # logo = models.ImageField(upload_to='vendor_image', null=True, blank=True)
    thumbnail = CloudinaryField('vendor_images', null=True, blank=True)
    logo = CloudinaryField('vendor_images', null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    category = models.ForeignKey('product.SystemCategory' , on_delete=models.SET_NULL, null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    open_time = models.TimeField(auto_now=True)
    close_time = models.TimeField(auto_now=True)
    bank_account = models.CharField(max_length=20,null=True,blank=True)
    bank_name = models.CharField(max_length=64,null=True,blank=True)
    bank_account_name = models.CharField(max_length=64,null=True,blank=True)
    estimated_delivery_time = models.DurationField(
        default=timedelta(minutes=30)
    )
    starting_delivery_price = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
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


    def __str__(self):
        return f"{self.name} ({self.user.email})"

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




MODE_OF_TRANSPORTATION = [
    ('bicycle', 'Bicycle'),
    ('bike', 'Bike'),
    ('car', 'Car'),
    ('van', 'Van'),
    ('truck', 'Truck'),
]

RIDER_STATUS = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('suspended', 'Suspended'),
    ('pending_verification', 'pending_verification'),
    ('document_rejected', 'Document rejected'),
]

RIDER_DOCUMENT_STATUS = [
    ('pending', 'apprpendingoved'),
    ('approved', 'approved'),
    ('submiited', 'submiited'),
    ('rejected', 'rejected'),
]



class Rider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    mode_of_transport = models.CharField(max_length=50, choices=MODE_OF_TRANSPORTATION)
    vehicle_number = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=50, choices=RIDER_STATUS, default='inactive')
    is_verified = models.BooleanField(default=False)
    document_status = models.CharField(max_length=50, choices=RIDER_DOCUMENT_STATUS, default='pending')
    
    # Add current location fields
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False, help_text="Whether the rider is currently online and available")


    # license docs
    # drivers_license_front = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the drivers license front.")
    # drivers_license_back = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the driver's license back.")
    # vehicle_insurance = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the vehicle's insurance.")
    # vehicle_registration = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the vehicle's registration certificate.")


    # Your existing document fields
    drivers_license_front = CloudinaryField('verification', blank=True, null=True, help_text="An image of the driver's license front.")
    drivers_license_back = CloudinaryField('verification', blank=True, null=True, help_text="An image of the driver's license back.")
    vehicle_insurance = CloudinaryField('verification', blank=True, null=True, help_text="An image of the vehicle's insurance.")
    vehicle_registration = CloudinaryField('verification', blank=True, null=True, help_text="An image of the vehicle's registration certificate.")

    def __str__(self):
        return f"Rider: "

    def update_location(self, latitude, longitude):
        from product.models import  DeliveryTracking
        """Update the rider's current location and propagate to active deliveries."""
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.location_updated_at = timezone.now()
        self.save()
        
        # Update all active delivery trackings for this rider
        active_orders = self.orders.filter(
            status__in=['picked_up', 'in_transit', 'near_delivery']
        )
        
        for order in active_orders:
            try:
                tracking = order.delivery_tracking.latest('updated_at')
                tracking.update_rider_location(latitude, longitude)
                
                # Check if rider is near delivery location and update status if needed
                if order.status == 'in_transit' and tracking.is_near_delivery_location():
                    order.mark_as_near_delivery()
                    
            except DeliveryTracking.DoesNotExist:
                # Create a new tracking entry if one doesn't exist
                DeliveryTracking.objects.create(
                    order=order,
                    rider_latitude=latitude,
                    rider_longitude=longitude
                )
    
    def go_online(self):
        """Set the rider as online and available for deliveries."""
        self.is_online = True
        self.save()
    
    def go_offline(self):
        """Set the rider as offline and unavailable for deliveries."""
        self.is_online = False
        self.save()
    
    @property
    def current_location(self):
        """Return the rider's current location as a dictionary."""
        if self.current_latitude and self.current_longitude:
            return {
                'latitude': self.current_latitude,
                'longitude': self.current_longitude,
                'updated_at': self.location_updated_at
            }
        return None
        
    @property
    def active_orders_count(self):
        """Return the count of active orders assigned to this rider."""
        return self.orders.filter(
            status__in=['confirmed', 'ready_for_pickup', 'picked_up', 'in_transit', 'near_delivery']
        ).count()



class RiderRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rider = models.ForeignKey(Rider, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.DecimalField(max_digits=3, decimal_places=2)  # e.g., 4.5 out of 5
    comment = models.TextField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('rider', 'user')  # Ensure each user can rate a vendor only once

    def __str__(self):
        return f"Rating for {self.rider.user.full_name} by {self.user.email}"



class VerificationCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE) 
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
            # generate a random four-digit number:: changed
            code = str(random.randint(1000, 9999))  
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    content = models.TextField(null=True,blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class VirtualAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=64, null=True,blank=True)
    bank_name = models.CharField(max_length=64, null=True,blank=True)
    provider_response = models.JSONField(default=dict)
    customer_reference = models.CharField(max_length=64, null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)





class FCMToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.TextField(unique=True)
    device_id = models.CharField(max_length=255, blank=True, null=True)
    platform = models.CharField(max_length=20, choices=[
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web')
    ], default='android')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'device_id']

    def __str__(self):
        return f"{self.user.username} - {self.platform}"

class PushNotificationLog(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    firebase_message_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"

