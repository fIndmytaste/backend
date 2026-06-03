import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()


class PromoCode(models.Model):
    """
    Model for promotional codes and discounts.
    """
    PROMO_TYPES = [
        ('free_delivery', 'Free Delivery'),
        ('discounted_delivery', 'Discounted Delivery'),
        ('fixed_amount', 'Fixed Amount Discount'),
        ('percentage', 'Percentage Discount'),
        ('referral', 'Referral Promo'),
        ('new_user', 'New User Promo'),
        ('automatic', 'Automatic / Direct Price Discount'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="The promo code (e.g., SAVE20). Optional for automatic promos.")
    description = models.TextField(null=True, blank=True, help_text="A brief description of this promo")
    promo_type = models.CharField(max_length=30, choices=PROMO_TYPES, default='fixed_amount')
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="The discount value (amount or percentage)")
    
    # Conditions
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Minimum order value to apply this promo")
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Maximum discount amount (for percentage promos)")
    usage_limit_per_user = models.PositiveIntegerField(default=1, help_text="How many times a single user can use this code")
    total_usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Total number of times this code can be used across all users")
    
    # Distance-based conditions
    max_distance_km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Maximum delivery distance for this promo")
    
    # Targets (M2M)
    applicable_zones = models.ManyToManyField('product.DeliveryZone', blank=True, related_name='promos')
    applicable_vendors = models.ManyToManyField('account.Vendor', blank=True, related_name='promos')
    applicable_categories = models.ManyToManyField('product.SystemCategory', blank=True, related_name='promos')
    applicable_customers = models.ManyToManyField(User, blank=True, related_name='targeted_promos', help_text="Specific users this promo is for")
    
    # Scheduling
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_automatic = models.BooleanField(default=False, help_text="Whether this discount is applied automatically without a code")
    
    # Referral & New User Specifics
    is_new_user_promo = models.BooleanField(default=False, help_text="Whether this promo is automatically applied to new users' first orders")
    referrer_reward_type = models.CharField(max_length=20, choices=(
        ('none', 'None'),
        ('wallet_credit', 'Wallet Credit'),
        ('fixed_amount', 'Fixed Amount Discount'),
        ('percentage', 'Percentage Discount'),
        ('free_delivery', 'Free Delivery'),
        ('discounted_delivery', 'Discounted Delivery'),
    ), default='none')
    referrer_reward_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="The value of the reward for the referrer")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'promo_codes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} ({self.get_promo_type_display()})"

    def is_valid_for_calculation(self, user=None, order_value=0, distance=None, vendor=None, zone=None, categories=None):
        """
        Check if the promo is valid for a given set of parameters.
        This is a preliminary check before applying.
        """
        now = timezone.now()
        
        if not self.is_active:
            return False, "Promo code is inactive"
        
        if self.start_date > now:
            return False, "Promo code is not yet active"
            
        if self.end_date and self.end_date < now:
            return False, "Promo code has expired"
            
        if order_value < self.min_order_value:
            return False, f"Minimum order value of {self.min_order_value} required"
            
        if self.total_usage_limit:
            usage_count = PromoUsage.objects.filter(promo=self).count()
            if usage_count >= self.total_usage_limit:
                return False, "Promo code has reached its total usage limit"
                
        if user and user.is_authenticated:
            # Check for new user promo
            if self.is_new_user_promo:
                from product.models import Order
                if Order.objects.filter(user=user).exclude(status='canceled').exists():
                    return False, "This promo is only for new users' first orders"
                    
            # Check targeted customers (skip if it's a new user promo)
            if not self.is_new_user_promo and self.applicable_customers.exists() and not self.applicable_customers.filter(id=user.id).exists():
                return False, "This promo is not available for your account"
                
            # Check usage limit per user
            user_usage_count = PromoUsage.objects.filter(promo=self, user=user).count()
            if user_usage_count >= self.usage_limit_per_user:
                return False, "You have reached the usage limit for this promo code"

        # Check distance
        if distance and self.max_distance_km and distance > self.max_distance_km:
            return False, f"Promo only applies to deliveries within {self.max_distance_km}km"

        # Check vendor
        if vendor and self.applicable_vendors.exists() and not self.applicable_vendors.filter(id=vendor.id).exists():
            return False, "Promo is not applicable for this vendor"

        # Check system category. Product categories are preferred when the
        # order context has them; vendor category is a safe fallback.
        if self.applicable_categories.exists():
            category_ids = set()
            if categories:
                for category in categories:
                    category_id = getattr(category, 'id', category)
                    if category_id:
                        category_ids.add(category_id)

            vendor_category_id = getattr(vendor, 'category_id', None) if vendor else None
            if vendor_category_id:
                category_ids.add(vendor_category_id)

            if not category_ids or not self.applicable_categories.filter(id__in=category_ids).exists():
                return False, "Promo is not applicable for this category"
            
        # Check zone
        if zone and self.applicable_zones.exists() and not self.applicable_zones.filter(id=zone.id).exists():
            return False, "Promo is not applicable in your current zone"

        return True, "Valid"


class PromoUsage(models.Model):
    """
    Log of promo code usage per order.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promo_usages')
    order = models.ForeignKey('product.Order', on_delete=models.CASCADE, related_name='promo_usages')
    
    # Store snapshot of values at time of use
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount before discount")
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount after discount")
    
    # Context
    distance_at_usage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'promo_usages'
        unique_together = ['promo', 'order'] # An order can only use a specific promo once

    def __str__(self):
        return f"{self.user.email} used {self.promo.code} on Order {self.order.id}"
