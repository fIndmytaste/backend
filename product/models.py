from datetime import timedelta
import uuid
import string
import random
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model
from django.db import transaction
from cloudinary.models import CloudinaryField
from product.promo_models import PromoCode


User = get_user_model()


def generate_track_id(length=8):
    """Generate a random alphanumeric string for track_id."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


class PlatformSettings(models.Model):
    """
    Singleton model to store global platform settings.
    Only one instance should exist.
    """
    default_commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text="Default platform commission percentage (e.g., 10.00 for 10%)"
    )
    delivery_percentage_off = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Global delivery discount (%)"
    )
    is_commission_active = models.BooleanField(
        default=True,
        help_text="Enable/disable commission calculation platform-wide"
    )
    rider_commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=(
            "Platform commission deducted from rider delivery fee before crediting "
            "the rider. E.g. 10.00 means rider keeps 90% of the delivery fee. "
            "Set to 0 to disable."
        )
    )

    # Rider Fare Configuration
    base_fare = models.DecimalField(
        max_digits=10, decimal_places=2, default=500.00)
    incremental_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=200.00)
    base_distance_range = models.DecimalField(
        max_digits=10, decimal_places=2, default=1.2)
    incremental_distance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.5)
    platform_operational_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=100.00)
    max_delivery_distance = models.DecimalField(
        max_digits=10, decimal_places=2, default=10.0)
    is_multi_stop_enabled = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Platform Settings (Commission: {self.default_commission_percentage}%)"


class DeliveryZone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(
        max_length=100,
        help_text="Name of the delivery zone. Example: 'Lekki Phase 1 Zone'"
    )

    boundary = models.JSONField(
        help_text=(
            "List of coordinates defining the zone boundary (Polygon). "
            "Coordinates should be provided as [latitude, longitude]. "
            "Example: [[6.5244, 3.3792], [6.5245, 3.3800], "
            "[6.5250, 3.3798], [6.5244, 3.3792]]"
        )
    )

    fixed_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Fixed delivery fee for this zone. Example: 1500.00"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Indicates whether this delivery zone is currently active."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Zone"
        verbose_name_plural = "Delivery Zones"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def contains_location(self, latitude, longitude):
        """
        Check if a given coordinate (lat, lng) is within this delivery zone's boundary.
        Uses the ray casting algorithm for point-in-polygon detection.
        
        Args:
            latitude (float): Location latitude
            longitude (float): Location longitude
        
        Returns:
            bool: True if the point is inside the zone, False otherwise
        """
        if not self.is_active or not self.boundary:
            return False
        
        try:
            polygon = self.boundary
            lat, lng = float(latitude), float(longitude)
            
            # Ray casting algorithm for point-in-polygon detection
            inside = False
            n = len(polygon)
            
            if n < 3:  # A polygon needs at least 3 points
                return False
            
            p1_lat, p1_lng = polygon[0]
            for i in range(1, n + 1):
                p2_lat, p2_lng = polygon[i % n]
                
                if lng > min(p1_lng, p2_lng):
                    if lng <= max(p1_lng, p2_lng):
                        if lat <= max(p1_lat, p2_lat):
                            if p1_lng != p2_lng:
                                x_intersect = (lng - p1_lng) * (p2_lat - p1_lat) / (p2_lng - p1_lng) + p1_lat
                            if p1_lat == p2_lat or lat <= x_intersect:
                                inside = not inside
                
                p1_lat, p1_lng = p2_lat, p2_lng
            
            return inside
        except (ValueError, TypeError, KeyError, IndexError):
            return False

    @classmethod
    def get_zone_for_location(cls, latitude, longitude):
        """
        Find the delivery zone that contains the given coordinates.
        
        Args:
            latitude (float): Location latitude
            longitude (float): Location longitude
        
        Returns:
            DeliveryZone or None: The zone containing the location, or None if not found
        """
        active_zones = cls.objects.filter(is_active=True)
        
        for zone in active_zones:
            if zone.contains_location(latitude, longitude):
                return zone
        
        return None

    @classmethod
    def get_rider_zone(cls, rider):
        """
        Find the delivery zone that contains a rider's current location.
        
        Args:
            rider: Rider instance with location_latitude and location_longitude
        
        Returns:
            DeliveryZone or None: The zone containing the rider, or None if not found
        """
        if not rider or not hasattr(rider, 'location_latitude') or not hasattr(rider, 'location_longitude'):
            return None
        
        if rider.location_latitude is None or rider.location_longitude is None:
            return None
        
        return cls.get_zone_for_location(rider.location_latitude, rider.location_longitude)


class EstateGatePass(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(
        max_length=100,
        help_text="Name of the estate or gate. Example: 'Banana Island Gate'"
    )

    location_zone = models.ForeignKey(
        DeliveryZone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estate_gates",
        help_text="Select the delivery zone this estate belongs to."
    )

    gate_fee_bike = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Gate pass fee charged for bike deliveries. Example: 500.00"
    )

    gate_fee_bus = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Gate pass fee charged for bus/van deliveries. Example: 1500.00"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Indicates whether this estate gate pass is active."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Estate Gate Pass"
        verbose_name_plural = "Estate Gate Passes"
        ordering = ["name"]

    def __str__(self):
        return self.name


# System Category model
class SystemCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, help_text="The name of the system category.")
    name_key = models.CharField(max_length=100, null=True, blank=True)
    logo = CloudinaryField('profile_images', null=True, blank=True)
    description = models.TextField(
        help_text="A detailed description of the system category.")
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the category was created.")
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the category was last updated.")
    is_stock = models.BooleanField(default=False)
    is_special_pricing = models.BooleanField(
        default=False, help_text="Enable special delivery pricing (50% discount on additional items). E.g., Fine Bites, Oyibo")
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custom commission rate for this category. Leave blank to use platform default."
    )
    delivery_percentage_off = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Delivery discount for this category (%)"
    )

    def __str__(self):
        return self.name


# Vendor Category model
class VendorCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, help_text="The name of the vendor category.")
    description = models.TextField(
        help_text="A detailed description of the vendor category.")
    vendor = models.ForeignKey('account.Vendor', on_delete=models.CASCADE,
                               help_text="The vendor associated with this category.")
    is_active = models.BooleanField(
        default=True, help_text="Indicates whether this vendor category is active or not.")
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the category was created.")
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the category was last updated.")

    def __str__(self):
        return self.name


# Product model
class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, help_text="The name of the product.")
    description = models.TextField(
        help_text="A detailed description of the product.")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="The regular price of the product.")
    system_category = models.ForeignKey('SystemCategory', on_delete=models.CASCADE, null=True,
                                        blank=True, help_text="The system category to which this product belongs.")
    category = models.ForeignKey('VendorCategory', on_delete=models.CASCADE,
                                 null=True, blank=True, help_text="The vendor category of this product.")
    # image = models.ImageField(upload_to='products/', blank=True, null=True, help_text="An image of the product.")
    stock = models.IntegerField(
        default=0, help_text="The number of units available in stock.")
    is_active = models.BooleanField(
        default=True, help_text="Indicates whether the product is active and available for sale.")
    is_delete = models.BooleanField(
        default=False, help_text="Indicates whether the product is marked for deletion.")
    is_featured = models.BooleanField(
        default=False, help_text="Indicates whether the product is marked for featured.")
    vendor = models.ForeignKey(
        'account.Vendor', on_delete=models.CASCADE, help_text="The vendor selling this product.")
    select_at_least_one_variant_enabled = models.BooleanField(default=True)

    starting_delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500.00,
        help_text="The starting delivery fee for this product.",
    )
    apply_discount = models.BooleanField(
        default=False, help_text="Indicates whether a discount is applied to this product.")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True,
                                              blank=True, help_text="The discount percentage on this product (e.g., 20 for 20%).")
    discount_start_date = models.DateTimeField(
        null=True, blank=True, help_text="The start date of the discount.")
    discount_end_date = models.DateTimeField(
        null=True, blank=True, help_text="The end date of the discount.")

    views = models.PositiveIntegerField(default=0)  # Track views
    purchases = models.PositiveIntegerField(default=0)  # Track purchases
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the product was created.")
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the product was last updated.")

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='variants',
        help_text="If this product is a variant, this points to the main product."
    )
    variant_category_name = models.CharField(
        max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_discounted_price(self):
        """
        Returns the discounted price if the discount is active, else returns the regular price.
        """
        from datetime import datetime

        # Check if the discount is active
        if self.apply_discount and self.discount_percentage and self.discount_start_date and self.discount_end_date:
            if self.discount_start_date <= datetime.now() <= self.discount_end_date:
                discount_amount = (self.discount_percentage / 100) * self.price
                return self.price - discount_amount
        return self.price

    def get_commission_rate(self):
        """
        Get the applicable commission rate for this product.
        Priority: Vendor-specific > Category-specific > Platform default

        Returns:
            Decimal: Commission percentage
        """
        return self.vendor.get_commission_rate()

    def calculate_commission(self, base_price=None):
        """
        Calculate commission amount for the product.

        Args:
            base_price: Optional specific price to calculate commission on.
                       If None, uses the product's discounted price or regular price.

        Returns:
            Decimal: Commission amount
        """
        from decimal import Decimal

        # # Check if vendor has custom rate
        # if  self.vendor.commission_percentage is not None:
        #     return self.vendor.commission_percentage

        # # Check if category has custom rate
        # if  self.vendor.category and self.vendor.category.commission_percentage is not None:
        #     return self.vendor.category.commission_percentage

        settings = PlatformSettings.get_settings()
        if not settings.is_commission_active:
            return Decimal('0.00')

        if base_price is None:
            base_price = self.get_discounted_price()

        rate = self.get_commission_rate() / Decimal('100')
        return (base_price * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_price_with_commission(self):
        """
        Get final price including commission (base price case).
        This is what the customer pays.

        Returns:
            Decimal: Price + Commission
        """
        return (self.price + self.calculate_commission(self.price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_discounted_price_with_commission(self):
        """
        Get discounted price including commission.

        Returns:
            Decimal: Discounted Price + Commission
        """
        discounted = self.get_discounted_price()
        return (discounted + self.calculate_commission(discounted)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_display_price(self):
        """
        Get the final price to display to customers (includes commission).
        Uses discounted price if available, otherwise regular price.

        Returns:
            Decimal: Final display price
        """
        return self.get_discounted_price_with_commission()

    def get_vendor_earnings(self, quantity=1):
        """
        Calculate what the vendor will receive (price without commission).

        Args:
            quantity: Number of units sold

        Returns:
            Decimal: Vendor earnings
        """
        from decimal import Decimal
        base_price = self.get_discounted_price()
        return (base_price * quantity).quantize(Decimal('0.01'))

    def get_platform_earnings(self, quantity=1):
        """
        Calculate platform commission earnings.

        Args:
            quantity: Number of units sold

        Returns:
            Decimal: Platform commission
        """
        from decimal import Decimal
        base_price = self.get_discounted_price()
        commission = self.calculate_commission(base_price)
        return (commission * quantity).quantize(Decimal('0.01'))

    def is_favorite(self):
        """
        Returns True if the product is in the user's favorites, otherwise False.
        """
        return None

    def all_images(self):
        """
        Returns a list of all images for this product, including the main image and all variant images.
        """
        images = [dict(
            id=image.id,
            image=image.get_image_url(),
        ) for image in ProductImage.objects.filter(product=self)]
        return images

    def increment_product_view(self, user):
        try:

            # Check if this user has already viewed the product
            if not ProductView.objects.filter(user=user, product=self).exists():
                with transaction.atomic():
                    ProductView.objects.create(user=user, product=self)
                    self.views += 1
                    self.save()

        except Product.DoesNotExist:
            raise ValueError("Product not found")


class ProductVariantCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category_name = models.CharField(
        max_length=100, help_text="The name of the product variant category.")
    parent_product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True,
                                       blank=True, help_text="The parent product to which this variant category belongs.")
    # child_products = models.ManyToManyField(Product, related_name='variant_categories', blank=True, help_text="The child products that belong to this variant category.")
    select_at_least_one_variant_enabled = models.BooleanField(default=True)
    allow_multiple_quantity = models.BooleanField(
        default=True,
        help_text="Indicates whether a user can select more than one quantity of the same variant."
    )
    allow_multiple_variant_selection = models.BooleanField(
        default=True,
        help_text="Indicates whether a user can select multiple different variants from this category."
    )
    max_quantity_per_variant = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of different variants a user can select from this category each. Leave blank for no limit."
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the product variant category was created.")
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the product variant category was last updated.")


# --- Variant Option Model ---
class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(ProductVariantCategory, on_delete=models.CASCADE,
                                 related_name='variants', help_text="The variant category this option belongs to.")
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='product_variants', help_text="The product this variant is for.")
    name = models.CharField(
        max_length=100, help_text="Name of the variant option, e.g., 'Rice'.")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price for this variant option.")
    stock = models.PositiveIntegerField(
        default=0, help_text="Stock for this variant option.")
    is_active = models.BooleanField(
        default=True, help_text="Is this variant option active?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.category.category_name})"

    def get_commission_rate(self):
        """
        Get the applicable commission rate for this variant.
        Uses the parent product's vendor commission rate.

        Returns:
            Decimal: Commission percentage
        """
        return self.product.get_commission_rate()

    def calculate_commission(self, base_price=None):
        """
        Calculate commission amount for the variant.

        Args:
            base_price: Optional specific price to calculate commission on.
                       If None, uses the variant's price.

        Returns:
            Decimal: Commission amount
        """
        from decimal import Decimal

        settings = PlatformSettings.get_settings()
        if not settings.is_commission_active:
            return Decimal('0.00')

        if base_price is None:
            base_price = self.price

        rate = self.get_commission_rate() / Decimal('100')
        return (Decimal(str(base_price)) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_price_with_commission(self):
        """
        Get final price including commission.
        This is what the customer pays for this variant.

        Returns:
            Decimal: Price + Commission
        """
        return (self.price + self.calculate_commission(self.price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# --- OrderItemVariant for tracking variant selections in orders ---
class OrderItemVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE, related_name='variant_selections',
                                   help_text="The order item this variant selection belongs to.")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, help_text="The selected variant option.")
    quantity = models.PositiveIntegerField(
        default=1, help_text="Quantity of this variant selected.")
    price_at_purchase = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price of the variant at the time of order.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.variant.name} x{self.quantity} for {self.order_item}"


class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # image = CloudinaryField('product_images', null=True, blank=True)
    image_url = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the product image was")
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the product image was last")
    is_primary = models.BooleanField(
        default=False, help_text="Is this the primary image for the product")
    is_active = models.BooleanField(
        default=True, help_text="Is this image active")

    def get_image_url(self):
        return self.image_url


class Order(models.Model):
    # Your existing fields...
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    PAYMENT_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PAID, 'Paid'),
        (FAILED, 'Failed'),
    ]

    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('looking_for_rider', 'Looking for Rider'),
        ('rider_assigned', 'Rider Assigned'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('near_delivery', 'Near Delivery Location'),
        ('delivered', 'Delivered'),
        ('canceled', 'Canceled'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
        ('payment_failed', 'Payment Failed'),
    ]
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'confirmed'),
        ('awaiting_rider', 'awaiting_rider'),
        ('rider_assigned', 'Rider Assigned'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('canceled', 'Canceled'),
    ]
    ORDER_PAYMENT_METHOD_CHOICES = [
        ('wallet', 'Wallet'),
        ('link', 'Link'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='orders', help_text="The user who placed the order.")
    vendor = models.ForeignKey('account.Vendor', on_delete=models.SET_NULL, null=True,
                               blank=True, related_name='vendors', help_text="The vendor who owns the order.")

    # Add the rider relationship
    rider = models.ForeignKey('account.Rider', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='orders', help_text="The rider assigned to deliver this order.")

    country = models.CharField(max_length=64, null=True, blank=True)
    state = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)
    address = models.CharField(max_length=256, null=True, blank=True)
    location_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    location_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the order was created.")
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the order was last updated.")

    # Update status choices
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES,
                              default='pending', help_text="The current status of the order.")

    # Promo and Discounts
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The total discount amount of the order (items + order level).")
    promo_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="Discount amount specifically from promo code.")
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The total amount of the order.")
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PENDING,
        help_text="The payment status of the order."
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='pending',
        help_text="The delivery status of the order."
    )
    delivery_otp = models.CharField(max_length=6, null=True, blank=True)
    delivery_otp_expiry = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The final delivery fee paid by the customer.")
    original_delivery_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The delivery fee before any promo/discount was applied.")
    rider_earning = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The amount the rider earns from this order.")
    delivery_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    service_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The service fee of the order.")
    track_id = models.CharField(
        max_length=100, help_text="Unique tracking ID per user")

    # Add estimated delivery time fieldsmodels.DurationField(

    new_estimated_pickup_time = models.DurationField(null=True, blank=True, default=timedelta(
        minutes=30), help_text="Estimated time when the rider will pick up the order.")
    new_estimated_delivery_time = models.DurationField(null=True, blank=True, default=timedelta(
        minutes=30), help_text="Estimated time when the order will be delivered.")

    # Add estimated times and distance for delivery tracking
    estimated_pickup_time = models.DateTimeField(
        null=True, blank=True, help_text="Estimated time when the rider will pick up the order.")
    estimated_dropoff_time = models.DateTimeField(
        null=True, blank=True, help_text="Estimated time when the order will be delivered to customer.")
    total_distance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, help_text="Total distance for delivery in kilometers.")

    # Add actual delivery time fields for metrics
    actual_pickup_time = models.DateTimeField(
        null=True, blank=True, help_text="Actual time when the rider picked up the order.")
    actual_delivery_time = models.DateTimeField(
        null=True, blank=True, help_text="Actual time when the order was delivered.")

    payment_method = models.CharField(max_length=20, choices=ORDER_PAYMENT_METHOD_CHOICES,
                                      default='wallet', help_text="The payment method of the order.")

    note = models.TextField(null=True, blank=True)


    vendor_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The amount that goes to the vendor after commission."
    )
    platform_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, help_text="The amount that goes to the platform as commission."
    )

    def __str__(self):
        return f"Order #{self.id}"

    def calculate_total_commission(self, prefetched_items=None):
        """Calculate total commission for all items in the order.

        Pass prefetched_items (already-evaluated list) to avoid re-querying the DB.
        """
        from decimal import Decimal
        total_commission = Decimal('0.00')

        items = prefetched_items if prefetched_items is not None else self.items.all()
        for item in items:
            product_commission = item.product.calculate_commission(item.price)
            total_commission += product_commission * item.quantity

            for variant_selection in item.variant_selections.all():
                variant_product = variant_selection.variant.product
                variant_commission = variant_product.calculate_commission(
                    variant_selection.price_at_purchase)
                total_commission += variant_commission * variant_selection.quantity * item.quantity

        return total_commission

    def update_total_amount(self):
        """Recalculates the total order amount based on order items."""
        items = self.items.prefetch_related('variant_selections').all()
        total = sum(item.total_price() for item in items)
        self.total_amount = total
        self.save()

    def save(self, *args, **kwargs):
        # Auto-generate track_id if it's not provided
        if not self.track_id and self.user:
            while True:
                new_track_id = generate_track_id()
                if not Order.objects.filter(user=self.user, track_id=new_track_id).exists():
                    self.track_id = new_track_id
                    break

        if not self.delivery_otp:
            self.delivery_otp = str(random.randint(10000, 99999))
            self.delivery_otp_expiry = timezone.now(
            ) + timedelta(minutes=15)  # expires in 15 minutes

        super().save(*args, **kwargs)

    def assign_rider(self, rider):
        """Assign a rider to this order and update status."""
        self.rider = rider
        self.status = 'rider_assigned'
        self.save()
        # Create a delivery tracking entry when a rider is assigned
        try:
            DeliveryTracking.objects.create(order=self)
        except:
            pass
        # notify user of about the accepted order via websoket
        # notify_user_of_accepted_order(self.user, self)

    def get_delivery_status(self):
        """Get detailed delivery status including rider location if available."""
        try:
            tracking = self.delivery_tracking.latest('updated_at')
            return {
                'status': self.status,
                'rider_name': self.rider.user.get_full_name() if self.rider else None,
                'rider_phone': self.rider.user.phone if self.rider and hasattr(self.rider.user, 'phone') else None,
                'rider_location': {
                    'latitude': tracking.rider_latitude,
                    'longitude': tracking.rider_longitude
                } if tracking and tracking.rider_latitude and tracking.rider_longitude else None,
                'estimated_delivery': self.estimated_delivery_time,
                'last_updated': tracking.updated_at if tracking else self.updated_at
            }
        except DeliveryTracking.DoesNotExist:
            return {
                'status': self.status,
                'last_updated': self.updated_at
            }

    def mark_as_picked_up(self):
        """Mark the order as picked up by the rider."""
        self.status = 'picked_up'
        self.actual_pickup_time = timezone.now()
        self.save()

    def mark_as_in_transit(self):
        """Mark the order as in transit."""
        self.status = 'in_transit'
        self.save()

    def mark_as_near_delivery(self):
        """Mark the order as near the delivery location."""
        self.status = 'near_delivery'
        self.save()

    def mark_as_delivered(self):
        """Mark the order as delivered."""
        self.status = 'delivered'
        self.actual_delivery_time = timezone.now()
        self.save()

    def get_estimated_delivery_duration(self):
        """
        Returns the estimated delivery duration in minutes.
        - Before pickup: Estimates based on Vendor -> Customer distance.
        - After pickup: Uses real-time Rider -> Customer tracking.
        """
        from math import radians, cos, sin, asin, sqrt

        # Helper for Haversine Distance (returns meters)
        def calculate_distance(lat1, lon1, lat2, lon2):
            if not all([lat1, lon1, lat2, lon2]):
                return 0

            try:
                lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
                lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                r = 6371000  # Radius of earth in meters
                return c * r
            except (ValueError, TypeError):
                return 0

        # Setup locations
        customer_lat = self.delivery_latitude or self.location_latitude
        customer_lon = self.delivery_longitude or self.location_longitude

        if customer_lat is None or customer_lon is None:
            return None  # Cannot estimate without destination

        # Determine phase
        # Statuses implying rider is active: 'picked_up', 'in_transit', 'near_delivery'
        active_delivery_statuses = ['picked_up', 'in_transit', 'near_delivery']
        is_active_delivery = self.status in active_delivery_statuses

        # Default speed: 20km/h = ~333 m/min (Average bike speed)
        AVERAGE_SPEED_M_MIN = 333

        if is_active_delivery:
            # Try to get latest rider tracking info
            try:
                # Accessing related DeliveryTracking objects
                # Note: Assuming 'product_delivery_trackings' is the related_name from DeliveryTracking model
                latest_tracking = self.product_delivery_trackings.latest(
                    'updated_at')

                # Option A: Use the pre-calculated time from tracking if valid
                if latest_tracking.estimated_time_remaining is not None:
                    return latest_tracking.estimated_time_remaining

                # Option B: Calculate using Rider's last known location
                if latest_tracking.rider_latitude is not None and latest_tracking.rider_longitude is not None:
                    dist_meters = calculate_distance(
                        latest_tracking.rider_latitude, latest_tracking.rider_longitude,
                        customer_lat, customer_lon
                    )
                    return int(dist_meters / AVERAGE_SPEED_M_MIN)

            except (AttributeError, ValueError, Exception):
                # Fallthrough to vendor estimate if tracking data is missing/error
                pass

        # Vendor -> Customer Estimate (Initial phase, or fallback if tracking fails)
        if self.vendor and self.vendor.location_latitude is not None and self.vendor.location_longitude is not None:
            dist_meters = calculate_distance(
                self.vendor.location_latitude, self.vendor.location_longitude,
                customer_lat, customer_lon
            )
            return int(dist_meters / AVERAGE_SPEED_M_MIN)

        return None

    def get_total_price(self):
        """Get the total price of the order."""
        order_items = OrderItem.objects.filter(order=self).prefetch_related('variant_selections')
        return sum(item.total_price() for item in order_items)

    def calculate_vendor_settlement_amount(self):
        """Calculate the vendor's actual take-home amount for the order."""
        from decimal import Decimal

        settlement_total = Decimal('0.00')
        for item in self.items.prefetch_related('variant_selections__variant').all():
            settlement_total += item.product.get_vendor_earnings(item.quantity)
            for variant_selection in item.variant_selections.all():
                settlement_total += (
                    variant_selection.variant.price * variant_selection.quantity * item.quantity
                )

        return settlement_total.quantize(Decimal('0.01'))

    def calculate_rider_earning_amount(self):
        """Calculate what should be credited to the rider for this order."""
        from decimal import Decimal

        candidate_amounts = [
            Decimal(str(self.rider_earning or 0)),
            Decimal(str(self.delivery_fee or 0)),
            Decimal(str(self.original_delivery_fee or 0)),
        ]
        return max(candidate_amounts).quantize(Decimal('0.01'))

    def calculate_net_rider_earning(self, gross_earning=None):
        """
        Apply the platform's rider commission to the gross delivery earning.

        The admin sets PlatformSettings.rider_commission_percentage (e.g. 10 for 10%).
        Rider receives: gross_earning * (1 - commission / 100).
        If commission is 0 or disabled the full gross amount is returned.
        """
        from decimal import Decimal
        gross = Decimal(str(gross_earning)) if gross_earning is not None else self.calculate_rider_earning_amount()
        settings = PlatformSettings.get_settings()
        commission_pct = Decimal(str(settings.rider_commission_percentage or 0))
        if commission_pct <= 0:
            return gross.quantize(Decimal('0.01'))
        net = gross * (1 - commission_pct / Decimal('100'))
        return max(Decimal('0.00'), net).quantize(Decimal('0.01'))


    def save_vendor_and_commision(self, gross_order_amount=None):
        """Persist the vendor settlement amount for this order."""
        try:
            total_vendor_amount = self.calculate_vendor_settlement_amount()
            if gross_order_amount is None:
                gross_order_amount = Decimal(str(self.get_total_price() or 0)).quantize(Decimal('0.01'))
            else:
                gross_order_amount = Decimal(str(gross_order_amount)).quantize(Decimal('0.01'))

            self.vendor_amount = total_vendor_amount
            self.platform_amount = max(
                Decimal('0.00'),
                (gross_order_amount - total_vendor_amount).quantize(Decimal('0.01')),
            )
            self.save()
        except Exception as e:
            print(f"Error calculating vendor and platform amounts: {e}")    

    # def get_vendor_earning(self):
    #     """Calculate total earnings for the vendor from this order."""
    #     from decimal import Decimal
    #     total_earning = Decimal('0.00')

    #     for item in self.items.all():
    #         total_earning += item.product.get_vendor_earnings(item.quantity)

    #         for variant_selection in item.variant_selections.all():
    #             variant_product = variant_selection.variant.product
    #             total_earning += variant_product.get_vendor_earnings(variant_selection.quantity)

    #     return total_earning

    class Meta:
        indexes = [
            models.Index(fields=['user', '-created_at'], name='order_user_created_idx'),
            models.Index(fields=['vendor', '-created_at'], name='order_vendor_created_idx'),
            models.Index(fields=['rider', '-created_at'], name='order_rider_created_idx'),
            models.Index(fields=['status'], name='order_status_idx'),
            models.Index(fields=['payment_status'], name='order_payment_status_idx'),
            models.Index(fields=['vendor', 'status'], name='order_vendor_status_idx'),
        ]


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items',
                              help_text="The order to which this item belongs.")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, help_text="The product in this order item.")
    quantity = models.PositiveIntegerField(
        default=1, help_text="The quantity of the product in the order.")
    price = models.DecimalField(max_digits=10, decimal_places=2,
                                help_text="Price of the product at the time of the order.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_price(self):
        """Returns the total price for this item (price * quantity + variant prices * quantity)."""
        total = self.price * self.quantity
        for variant_selection in self.variant_selections.all():
            total += variant_selection.price_at_purchase * variant_selection.quantity * self.quantity
        return total

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"

    class Meta:
        indexes = [
            models.Index(fields=['order'], name='orderitem_order_idx'),
            models.Index(fields=['product'], name='orderitem_product_idx'),
        ]


class DeclinedOrder(models.Model):
    rider = models.ForeignKey(
        'account.Rider', on_delete=models.CASCADE, related_name='declined_orders')
    order = models.ForeignKey(
        'Order', on_delete=models.CASCADE, related_name='declined_by_riders')
    declined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent multiple declines for same order
        unique_together = ('rider', 'order')


class Rating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.DecimalField(
        max_digits=2, decimal_places=1)  # e.g., 4.5 out of 5
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures each user can rate a product only once
        unique_together = ('product', 'user')

    def __str__(self):
        return f"Rating for {self.product.name} by {self.user.username}"


class UserFavoriteVendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='favorites')
    vendor = models.ForeignKey('account.Vendor', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A user can only favorite a product once
        unique_together = ['user', 'vendor']

    def __str__(self):
        return f"{self.user} - {self.vendor}"


class ProductView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure that each user can view the product only once
        unique_together = ('user', 'product')


class DeliveryTracking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        'Order', on_delete=models.CASCADE, related_name='product_delivery_trackings')

    # Rider's current location during delivery
    rider_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    rider_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    # Timestamps for tracking events
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Distance and time estimates
    distance_to_delivery = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                               help_text="Estimated distance to delivery in meters")
    estimated_time_remaining = models.IntegerField(null=True, blank=True,
                                                   help_text="Estimated time remaining in minutes")

    def __str__(self):
        return f"Tracking for Order #{self.order.id}"

    def update_rider_location(self, latitude, longitude):
        """Update the rider's location and recalculate estimates."""
        self.rider_latitude = latitude
        self.rider_longitude = longitude

        # Calculate distance to delivery location
        if self.order.location_latitude and self.order.location_longitude:
            self.distance_to_delivery = self.calculate_distance_to_delivery()
            self.estimated_time_remaining = self.calculate_estimated_time()

        self.save()

    def calculate_distance_to_delivery(self):
        """Calculate distance from rider to delivery location using Haversine formula."""
        from math import radians, cos, sin, asin, sqrt

        # Get coordinates
        rider_lat = float(self.rider_latitude)
        rider_lng = float(self.rider_longitude)
        dest_lat = float(self.order.location_latitude)
        dest_lng = float(self.order.location_longitude)

        # Convert decimal degrees to radians
        rider_lat, rider_lng, dest_lat, dest_lng = map(
            radians, [rider_lat, rider_lng, dest_lat, dest_lng])

        # Haversine formula
        dlng = dest_lng - rider_lng
        dlat = dest_lat - rider_lat
        a = sin(dlat/2)**2 + cos(rider_lat) * cos(dest_lat) * sin(dlng/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Radius of earth in meters

        return c * r

    def calculate_estimated_time(self):
        """Estimate delivery time based on distance and rider's mode of transportation."""
        if not self.distance_to_delivery:
            return None

        # Get the rider's speed based on transportation mode
        rider = self.order.rider
        if not rider:
            return None

        # Estimated speeds in meters per minute for different transportation modes
        speeds = {
            'bicycle': 200,  # ~12 km/h
            'bike': 333,     # ~20 km/h
            'car': 500,      # ~30 km/h
            'van': 500,      # ~30 km/h
            'truck': 417     # ~25 km/h
        }

        # Default to bike speed
        speed = speeds.get(rider.mode_of_transport, 333)

        # Calculate time in minutes
        return round(self.distance_to_delivery / speed)

    def is_near_delivery_location(self, threshold_meters=200):
        """Check if the rider is within threshold_meters of the delivery location."""
        if not self.distance_to_delivery:
            return False

        return self.distance_to_delivery <= threshold_meters

    def send_tracking_update(self):
        """Send tracking update through WebSockets."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        room_group_name = f'order_tracking_{self.order.id}'

        # Send tracking data to the channel group
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'tracking_update',
                'tracking_data': self.order.get_delivery_status()
            }
        )

    # Then call this method in update_rider_location:
    def update_rider_location(self, latitude, longitude):
        """Update the rider's location and recalculate estimates."""
        self.rider_latitude = latitude
        self.rider_longitude = longitude

        # Calculate distance to delivery location
        if self.order.location_latitude and self.order.location_longitude:
            self.distance_to_delivery = self.calculate_distance_to_delivery()
            self.estimated_time_remaining = self.calculate_estimated_time()

        self.save()

        # Send real-time update
        self.send_tracking_update()


class DeliveryFee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.FloatField(default=0)
    original_amount = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    vendor = models.ForeignKey('account.Vendor', on_delete=models.CASCADE)
