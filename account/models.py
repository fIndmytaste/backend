import random
import uuid
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from cloudinary.models import CloudinaryField
from datetime import timedelta

from helpers.order_utils import calculate_delivery_fee
from vendor.models import MarketPlace


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
    # profile_image = CloudinaryField('profile_images', null=True, blank=True)
    profile_image_url = models.TextField(null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    is_verified = models.BooleanField(default=False, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bank_account = models.CharField(max_length=20, null=True, blank=True)
    bank_name = models.CharField(max_length=64, null=True, blank=True)
    bank_account_name = models.CharField(max_length=64, null=True, blank=True)
    dob = models.CharField(max_length=5, null=True, blank=True,
                           help_text="Date of birth in MM-DD format (e.g., 03-15)")
    delivery_percentage_off = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Delivery discount for this user (%)"
    )
    role = models.CharField(max_length=10, choices=(
        ('admin', 'Admin'),
        ('buyer', 'buyer'),
        ('vendor', 'vendor'),
        ('rider', 'rider'),
    ), default='buyer')

    referral_code = models.CharField(
        max_length=20, unique=True, null=True, blank=True, db_index=True)
    referred_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrees')

    objects = UserManager()
    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email

    @classmethod
    def generate_referral_code(cls, full_name):
        """Generate a unique referral code based on the user's name."""
        import string
        import random

        prefix = "FMT"
        if full_name:
            # Take first 3 letters of name, uppercase, remove non-alphanumeric
            clean_name = "".join(filter(str.isalnum, full_name)).upper()
            if clean_name:
                prefix = clean_name[:4]

        while True:
            suffix = ''.join(random.choices(
                string.ascii_uppercase + string.digits, k=4))
            code = f"{prefix}{suffix}"
            if not cls.objects.filter(referral_code=code).exists():
                return code

    def get_profile_image(self):
        return self.profile_image_url

    def get_full_name(self):
        return self.full_name if self.full_name else self.email

    def username(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code(self.full_name)
        super().save(*args, **kwargs)

    @property
    def referral_free_bonus(self):
        """
        Returns a list of unused referral bonus promo codes for this user,
        including full details: expiry, min order value, discount cap, usage
        limits, distance limit, and computed status flags.
        """
        from django.utils import timezone as tz
        from product.promo_models import PromoCode

        if not self.referral_code:
            return []

        now = tz.now()

        unused_promos = PromoCode.objects.filter(
            code__startswith=f"REF-{self.referral_code[:4].upper()}",
            applicable_customers=self,
            is_active=True,
        ).exclude(usages__user=self)

        result = []
        for p in unused_promos:
            # How many times this user has already used it
            times_used = p.usages.filter(user=self).count()
            uses_remaining = max(0, p.usage_limit_per_user - times_used)

            # Expiry helpers
            is_expired = bool(p.end_date and p.end_date < now)
            days_remaining = None
            if p.end_date and not is_expired:
                days_remaining = (p.end_date.date() - now.date()).days

            result.append({
                "code": p.code,
                "description": p.description,
                "promo_type": p.promo_type,
                "promo_type_display": p.get_promo_type_display(),

                # Discount value
                "value": float(p.value),
                "max_discount": float(p.max_discount) if p.max_discount is not None else None,

                # Conditions
                "min_order_value": float(p.min_order_value),
                "max_distance_km": float(p.max_distance_km) if p.max_distance_km is not None else None,

                # Usage
                "usage_limit_per_user": p.usage_limit_per_user,
                "times_used": times_used,
                "uses_remaining": uses_remaining,

                # Validity window
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "expiry_date": p.end_date.isoformat() if p.end_date else None,
                "is_expired": is_expired,
                "days_remaining": days_remaining,
                "is_active": p.is_active,
            })

        return result


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    country = models.CharField(max_length=64)
    state = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)

    address = models.TextField(null=True, blank=True)
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
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=64, null=True, blank=True)
    state = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)
    address = models.CharField(max_length=256, null=True, blank=True)
    location_latitude = models.CharField(max_length=20, null=True, blank=True)
    location_longitude = models.CharField(max_length=20, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    # logo = models.ImageField(upload_to='vendor_image', null=True, blank=True)
    # thumbnail = CloudinaryField('vendor_images', null=True, blank=True)
    thumbnail_url = models.TextField(null=True, blank=True)
    # logo = CloudinaryField('vendor_images', null=True, blank=True)
    logo_url = models.TextField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    approval_status = models.CharField(max_length=10, choices=(
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ), default='pending')
    approval_comment = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        'product.SystemCategory', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    bank_account = models.CharField(max_length=20, null=True, blank=True)
    bank_name = models.CharField(max_length=64, null=True, blank=True)
    is_marketplace = models.BooleanField(default=False)
    bank_account_name = models.CharField(max_length=64, null=True, blank=True)
    estimated_delivery_time = models.DurationField(
        default=timedelta(minutes=30)
    )
    starting_delivery_price = models.DecimalField(
        max_digits=9, decimal_places=6, default=0.0)
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
    delivery_radius_km = models.DecimalField(
        max_digits=10, decimal_places=2, default=10.0)
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custom commission rate for this vendor. Leave blank to use category or platform default."
    )
    marketplace_delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override base delivery fee for this vendor when in a marketplace. Leave blank to use marketplace default."
    )

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    def is_currently_open(self):
        if not self.is_active or self.approval_status != 'approved':
            return False

        if not self.open_time or not self.close_time:
            return True

        day_names = [
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday',
            'Friday',
            'Saturday',
            'Sunday',
        ]

        now = timezone.localtime()
        current_day_index = now.weekday()
        current_time = now.time()

        try:
            open_day_index = day_names.index(self.open_day)
            close_day_index = day_names.index(self.close_day)
        except ValueError:
            return True

        def day_in_range(day_index):
            if open_day_index <= close_day_index:
                return open_day_index <= day_index <= close_day_index
            return day_index >= open_day_index or day_index <= close_day_index

        today_ok = day_in_range(current_day_index)

        open_minutes = self.open_time.hour * 60 + self.open_time.minute
        close_minutes = self.close_time.hour * 60 + self.close_time.minute
        now_minutes = current_time.hour * 60 + current_time.minute

        if open_minutes == close_minutes:
            return today_ok

        # Overnight window, e.g. 20:00 -> 03:00
        if close_minutes < open_minutes:
            if today_ok and now_minutes >= open_minutes:
                return True

            yesterday_index = (current_day_index - 1) % 7
            yesterday_ok = day_in_range(yesterday_index)
            return yesterday_ok and now_minutes < close_minutes

        return today_ok and open_minutes <= now_minutes < close_minutes

    def get_closed_message(self):
        if not self.is_active:
            return "This vendor is currently unavailable."

        if self.approval_status != 'approved':
            return "This vendor is currently unavailable."

        if self.is_currently_open():
            return ""

        if self.open_time and self.close_time:
            open_label = self.open_time.strftime('%I:%M %p')
            close_label = self.close_time.strftime('%I:%M %p')
            return f"{self.name} is currently closed. Opens {self.open_day} {open_label} - {self.close_day} {close_label}."

        return f"{self.name} is currently closed."

    def get_commission_rate(self):
        """
        Get the applicable commission rate for this vendor.
        Priority: Vendor-specific > Category-specific > Platform default

        Returns:
            Decimal: Commission percentage
        """
        from product.models import PlatformSettings

        # Check if vendor has custom rate
        if self.commission_percentage is not None:
            return self.commission_percentage

        # Check if category has custom rate
        if self.category and self.category.commission_percentage is not None:
            return self.category.commission_percentage

        # Use platform default
        settings = PlatformSettings.get_settings()
        return settings.default_commission_percentage

    def calculate_delivery_fee_by_vendor(self, item_count=1, dest_lat=None, dest_lon=None, user=None, promo_code=None, order_value=0.0):
        """
        Calculate delivery fee based on marketplace settings and category type, applying delivery_percentage_off logic.
        """
        import logging
        from decimal import Decimal
        from product.models import PlatformSettings
        from helpers.order_utils import apply_promo_code, get_distance_between_two_location
        logger = logging.getLogger(__name__)
        delivery_fee = None
        promo_info = {"is_applied": False, "discount_amount": 0, "affects_delivery": False}
        service_fee = Decimal('0.00')
        is_in_marketplace = MarketPlace.objects.filter(vendors=self).first()
        logger.info(
            "[delivery_fee] vendor=%s is_in_marketplace=%s item_count=%s",
            self.id, bool(is_in_marketplace), item_count,
        )
        if not is_in_marketplace:
            # Non-marketplace vendors use their own pricing
            delivery_fee_info = calculate_delivery_fee(
                origin_lat=float(self.location_latitude),
                origin_lon=float(self.location_longitude),
                dest_lat=float(dest_lat),
                dest_lon=float(dest_lon),
                item_count=item_count,
                user_id=str(user.id) if user else None,
                promo_code=promo_code,
                order_value=order_value
            )
            delivery_fee = delivery_fee_info['total_fee']
            original_delivery_fee = delivery_fee_info['original_fee']
            promo_info = delivery_fee_info.get(
                'promo_info', {"is_applied": False, "discount_amount": 0})
        else:
            if item_count <= 0:
                return {
                    "total_fee": Decimal('0.00'),
                    "original_fee": Decimal('0.00'),
                    "promo_info": promo_info,
                }
            # Access marketplace via reverse relationship
            # marketplace = self.marketplace_set.first()
            marketplace = MarketPlace.objects.filter(vendors=self).first()
            if not marketplace:
                # Fallback to vendor's own pricing if no marketplace found
                delivery_fee_info = calculate_delivery_fee(
                    origin_lat=float(self.location_latitude),
                    origin_lon=float(self.location_longitude),
                    dest_lat=float(dest_lat),
                    dest_lon=float(dest_lon),
                    item_count=item_count,
                    user_id=str(user.id) if user else None,
                    promo_code=promo_code,
                    order_value=order_value
                )
                delivery_fee = delivery_fee_info['total_fee']
                original_delivery_fee = delivery_fee_info['original_fee']
                promo_info = delivery_fee_info.get(
                    'promo_info', {"is_applied": False, "discount_amount": 0})
            else:
                # Marketplace follows fixed admin-configured item-count pricing.
                # Per-vendor override takes priority over marketplace default base fee.
                vendor_base_fee = (
                    self.marketplace_delivery_fee
                    if self.marketplace_delivery_fee is not None
                    else marketplace.delivery_fee
                )
                is_special_category = (
                    self.category and
                    hasattr(self.category, 'is_special_pricing') and
                    self.category.is_special_pricing
                )
                logger.info(
                    "[delivery_fee] marketplace=%s base_fee=%s (vendor_override=%s) "
                    "second_item_fee=%s additional_item_fee=%s special_discount=%s is_special_category=%s",
                    marketplace.id, vendor_base_fee, self.marketplace_delivery_fee,
                    marketplace.second_item_fee, marketplace.additional_item_fee,
                    marketplace.special_category_discount_percentage, is_special_category,
                )
                if is_special_category:
                    # SPECIAL PRICING: First item full price, additional items discounted
                    base_fee = vendor_base_fee
                    discount = marketplace.special_category_discount_percentage / \
                        Decimal('100')
                    if item_count == 1:
                        delivery_fee = base_fee
                    else:
                        # First item + (additional items at discounted rate)
                        additional_items = item_count - 1
                        discounted_fee = base_fee * (Decimal('1') - discount)
                        total = base_fee + (discounted_fee * additional_items)
                        delivery_fee = total.quantize(Decimal('0.01'))
                else:
                    # STANDARD PRICING: Progressive pricing structure
                    if item_count == 1:
                        delivery_fee = vendor_base_fee
                    elif item_count == 2:
                        total = vendor_base_fee + marketplace.second_item_fee
                        delivery_fee = total.quantize(Decimal('0.01'))
                    else:
                        # Base (first 2 items) + additional items
                        base_for_two = vendor_base_fee + marketplace.second_item_fee
                        additional_items = item_count - 2
                        total = base_for_two + \
                            (marketplace.additional_item_fee * additional_items)
                        delivery_fee = total.quantize(Decimal('0.01'))
                service_fee = Decimal('0.00')
                logger.info("[delivery_fee] calculated delivery_fee=%s", delivery_fee)

        # --- DELIVERY PERCENTAGE OFF LOGIC ---
        delivery_discount_percentage = None
        # 1. User-specific
        if user and hasattr(user, 'delivery_percentage_off') and user.delivery_percentage_off is not None:
            delivery_discount_percentage = user.delivery_percentage_off
        # 2. Category-specific
        elif self.category and hasattr(self.category, 'delivery_percentage_off') and self.category.delivery_percentage_off is not None:
            delivery_discount_percentage = self.category.delivery_percentage_off
        # 3. Platform/global
        else:
            try:
                platform_settings = PlatformSettings.get_settings()
                if platform_settings.delivery_percentage_off is not None:
                    delivery_discount_percentage = platform_settings.delivery_percentage_off
            except Exception:
                pass
        # Apply delivery percentage off
        original_delivery_fee = delivery_fee  # Save before platform percentage discount
        if delivery_fee is not None and delivery_discount_percentage is not None and delivery_discount_percentage > 0:
            discount_amount = (
                Decimal(delivery_discount_percentage) / Decimal('100')) * Decimal(delivery_fee)
            delivery_fee = Decimal(delivery_fee) - discount_amount

        # Manual promo handling for the marketplace path.
        if is_in_marketplace:
            # delivery_fee may be None if marketplace lookup failed
            if delivery_fee is None:
                delivery_fee = Decimal('0.00')

            if promo_code and delivery_fee > 0:
                distance_km = 0.0
                if dest_lat and dest_lon:
                    try:
                        distance_km = get_distance_between_two_location(
                            lat1=float(self.location_latitude),
                            lon1=float(self.location_longitude),
                            lat2=float(dest_lat),
                            lon2=float(dest_lon),
                        )
                    except Exception:
                        pass

                try:
                    promo_info = apply_promo_code(
                        promo_code=promo_code,
                        user_obj=user,
                        order_value=float(order_value),
                        distance_km=distance_km,
                        vendor_obj=self,
                        current_fee=float(delivery_fee),
                    )
                except Exception:
                    promo_info = {"is_applied": False, "affects_delivery": False, "discount_amount": 0}

            if promo_info["is_applied"] and promo_info["affects_delivery"]:
                delivery_fee = Decimal(delivery_fee) - \
                    Decimal(str(promo_info["discount_amount"]))
                delivery_fee = max(Decimal('0.00'), delivery_fee)

            total_fee = delivery_fee + service_fee
            if promo_info["is_applied"] and not promo_info["affects_delivery"]:
                total_fee -= Decimal(str(promo_info["discount_amount"]))
            total_fee = max(Decimal('0.00'), total_fee)
        else:
            total_fee = Decimal(str(delivery_fee))

        result = {
            "total_fee": Decimal(total_fee).quantize(Decimal('0.01')) if delivery_fee is not None else Decimal('0.00'),
            "original_fee": Decimal(original_delivery_fee).quantize(Decimal('0.01')) if original_delivery_fee is not None else Decimal('0.00'),
            "promo_info": promo_info,
            "service_fee": service_fee.quantize(Decimal('0.01')) if isinstance(service_fee, Decimal) else Decimal('0.00'),
        }
        logger.info("[delivery_fee] returning total_fee=%s original_fee=%s", result["total_fee"], result["original_fee"])
        return result


class VendorRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        Vendor, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.DecimalField(
        max_digits=3, decimal_places=2)  # e.g., 4.5 out of 5
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensure each user can rate a vendor only once
        unique_together = ('vendor', 'user')

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
    ('suspended', 'Suspended')
]

RIDER_DOCUMENT_STATUS = [
    ('pending', 'pending'),
    ('approved', 'approved'),
    ('submitted', 'submitted'),
    ('rejected', 'rejected'),
]


class Rider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    mode_of_transport = models.CharField(
        max_length=50, choices=MODE_OF_TRANSPORTATION)
    vehicle_number = models.CharField(max_length=20, null=True, blank=True)
    vehicle_brand = models.CharField(max_length=64, null=True, blank=True)
    plate_number = models.CharField(max_length=32, null=True, blank=True)
    next_of_kin = models.CharField(max_length=64, null=True, blank=True)
    next_of_kin_phone = models.CharField(max_length=32, null=True, blank=True)
    preferred_location = models.CharField(
        max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(
        max_length=50, choices=RIDER_STATUS, default='inactive')
    is_verified = models.BooleanField(default=False)
    document_status = models.CharField(
        max_length=50, choices=RIDER_DOCUMENT_STATUS, default='pending')

    # Add current location fields
    current_latitude = models.DecimalField(
        max_digits=19, decimal_places=16, null=True, blank=True)
    current_longitude = models.DecimalField(
        max_digits=19, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(
        default=False, help_text="Whether the rider is currently online and available")
    is_in_house_rider = models.BooleanField(
        default=False, help_text="Marketplace riders are in-house and receive a fixed salary")
    salary = models.DecimalField(max_digits=12, decimal_places=2,
                                 default=0.00, help_text="Monthly salary for in-house riders")

    # Performance metrics (cached/denormalized for quick access)
    on_time_delivery_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00)
    successful_delivery_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00)
    order_acceptance_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00)
    average_customer_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00)

    # license docs
    # drivers_license_front = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the drivers license front.")
    # drivers_license_back = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the driver's license back.")
    # vehicle_insurance = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the vehicle's insurance.")
    # vehicle_registration = models.ImageField(upload_to='verification/', blank=True, null=True, help_text="An image of the vehicle's registration certificate.")

    # Your existing document fields
    drivers_license_front = CloudinaryField(
        'verification', blank=True, null=True, help_text="An image of the driver's license front.")
    drivers_license_back = CloudinaryField(
        'verification', blank=True, null=True, help_text="An image of the driver's license back.")
    nin_front = CloudinaryField(
        'verification', blank=True, null=True, help_text="An image of the NIN front.")
    nin_back = CloudinaryField(
        'verification', blank=True, null=True, help_text="An image of the NIN back.")
    vehicle_insurance = CloudinaryField(
        'verification', blank=True, null=True, help_text="An image of the vehicle's insurance.")
    vehicle_registration = CloudinaryField(
        'verification', blank=True, null=True, help_text="An image of the vehicle's registration certificate.")

    country = models.CharField(max_length=64, null=True, blank=True)
    state = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)
    address = models.CharField(max_length=256, null=True, blank=True)
    location_latitude = models.CharField(max_length=20, null=True, blank=True)
    location_longitude = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"Rider: "

    def update_location(self, latitude, longitude):
        from helpers.redis_rider_geo import geo_add_rider
        """Update the rider's current location and propagate to active deliveries."""
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.location_updated_at = timezone.now()
        self.save()
        self.refresh_from_db()  # Ensure we have the latest data after save()
        if self.is_online:
            geo_add_rider(self)

        print(
            "Rider updated location :: ", self.current_latitude, self.current_longitude, self.location_updated_at
        )
        # Update all active delivery trackings for this rider
        # for order in active_orders:
        #     try:
        #         tracking = order.delivery_tracking.latest('updated_at')
        #         tracking.update_rider_location(latitude, longitude)

        #         # Check if rider is near delivery location and update status if needed
        #         if order.status == 'in_transit' and tracking.is_near_delivery_location():
        #             order.mark_as_near_delivery()

        #     except DeliveryTracking.DoesNotExist:
        #         # Create a new tracking entry if one doesn't exist
        #         DeliveryTracking.objects.create(
        #             order=order,
        #             rider_latitude=latitude,
        #             rider_longitude=longitude
        #         )

    def go_online(self):
        """Set the rider as online and available for deliveries."""
        from helpers.redis_rider_geo import geo_add_rider
        self.is_online = True
        self.save()
        geo_add_rider(self)

    def go_offline(self):
        """Set the rider as offline and unavailable for deliveries."""
        from product.models import Order
        from helpers.redis_rider_geo import geo_remove_rider
        active_orders = Order.objects.filter(
            rider=self,
            status__in=['rider_assigned', 'picked_up',
                        'in_transit', 'near_delivery']
        ).exists()
        if active_orders:
            raise ValueError(
                "Cannot go offline while you have active deliveries")
        self.is_online = False
        self.save()
        geo_remove_rider(self.id)

    def update_performance_metrics(self):
        """Calculate and update rider performance metrics."""
        from product.models import Order
        from django.db.models import Avg
        from decimal import Decimal

        orders = Order.objects.filter(rider=self)
        total_orders = orders.count()
        if total_orders == 0:
            return

        completed_orders = orders.filter(status='delivered').count()
        self.successful_delivery_rate = Decimal(
            str(min(100.0, (completed_orders / total_orders) * 100)))

        # Average customer rating
        avg_rating = RiderRating.objects.filter(
            rider=self).aggregate(Avg('rating'))['rating__avg']
        if avg_rating:
            self.average_customer_rating = Decimal(str(avg_rating))

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
            status__in=['rider_assigned', 'confirmed', 'ready_for_pickup',
                        'picked_up', 'in_transit', 'near_delivery']
        ).count()

    def get_current_zone(self):
        """
        Get the delivery zone the rider is currently in based on their current location.

        Returns:
            DeliveryZone or None: The zone containing the rider's current location, or None
        """
        from product.models import DeliveryZone

        if self.current_latitude and self.current_longitude:
            try:
                return DeliveryZone.get_zone_for_location(
                    float(self.current_latitude),
                    float(self.current_longitude)
                )
            except (ValueError, TypeError):
                pass
        return None

    def get_home_zone(self):
        """
        Get the delivery zone for the rider's registered home location.

        Returns:
            DeliveryZone or None: The zone containing the rider's home location, or None
        """
        from product.models import DeliveryZone

        if self.location_latitude and self.location_longitude:
            try:
                return DeliveryZone.get_zone_for_location(
                    float(self.location_latitude),
                    float(self.location_longitude)
                )
            except (ValueError, TypeError):
                pass
        return None

    def is_in_zone(self, zone):
        """
        Check if the rider is currently in a specific delivery zone.

        Args:
            zone: DeliveryZone instance

        Returns:
            bool: True if rider is in the zone, False otherwise
        """
        current_zone = self.get_current_zone()
        return current_zone == zone if current_zone else False


class Guarantor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rider = models.ForeignKey(
        Rider, related_name='guarantors', on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    phone_number = models.CharField(max_length=32)
    relationship = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Guarantor: {self.name} for {self.rider.user.full_name if self.rider and self.rider.user else self.rider_id}"


class RiderRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rider = models.ForeignKey(
        Rider, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.DecimalField(
        max_digits=3, decimal_places=2)  # e.g., 4.5 out of 5
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensure each user can rate a vendor only once
        unique_together = ('rider', 'user')

    def __str__(self):
        return f"Rating for {self.rider.user.full_name} by {self.user.email}"


class VerificationCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    verification_type = models.CharField(
        max_length=32,
        choices=[
            ('email', 'Email Verification'),
            ('phone', 'Phone Verification'),
            ('password', 'Password Reset'),
        ],
        null=True,
        blank=True,

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
    content = models.TextField(null=True, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class VirtualAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=64, null=True, blank=True)
    bank_name = models.CharField(max_length=64, null=True, blank=True)
    provider_response = models.JSONField(default=dict)
    customer_reference = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FCMToken(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='fcm_tokens')
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
        return f"{self.user.id} - {self.platform}"


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
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='sent')
    firebase_message_id = models.CharField(
        max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class VendorIssueReporting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
