# Platform Commission System - Usage Examples

## Overview
The platform now supports a flexible commission structure with three levels of priority:
1. **Vendor-specific** commission (highest priority)
2. **Category-specific** commission
3. **Platform default** commission (lowest priority)

---

## Setup

### 1. Configure Platform Default Commission
```python
from product.models import PlatformSettings

# Get or create settings
settings = PlatformSettings.get_settings()
settings.default_commission_percentage = 10.00  # 10%
settings.is_commission_active = True
settings.save()
```

### 2. Set Category-Specific Commission (Optional)
```python
from product.models import SystemCategory

# Override commission for specific category
fine_bites = SystemCategory.objects.get(name="Fine Bites")
fine_bites.commission_percentage = 15.00  # 15% for Fine Bites
fine_bites.save()
```

### 3. Set Vendor-Specific Commission (Optional)
```python
from account.models import Vendor

# Override commission for specific vendor
vendor = Vendor.objects.get(name="Premium Restaurant")
vendor.commission_percentage = 12.00  # 12% for this vendor
vendor.save()
```

---

## Product Pricing Examples

### Example 1: Basic Product (Platform Default)
```python
from product.models import Product

product = Product.objects.get(id=product_id)

# Original vendor price
print(f"Vendor Price: ₦{product.price}")  
# Output: Vendor Price: ₦10,000

# Commission calculation
print(f"Commission Rate: {product.get_commission_rate()}%")
# Output: Commission Rate: 10.0%

print(f"Commission Amount: ₦{product.calculate_commission()}")
# Output: Commission Amount: ₦1,000

# Price shown to customer
print(f"Customer Pays: ₦{product.get_display_price()}")
# Output: Customer Pays: ₦11,000
```

### Example 2: Product with Discount
```python
product.price = 10000
product.apply_discount = True
product.discount_percentage = 20  # 20% discount
product.save()

# Discounted vendor price
print(f"Discounted Price: ₦{product.get_discounted_price()}")
# Output: Discounted Price: ₦8,000

# Commission on discounted price
print(f"Commission: ₦{product.calculate_commission()}")
# Output: Commission: ₦800

# Final price to customer
print(f"Customer Pays: ₦{product.get_display_price()}")
# Output: Customer Pays: ₦8,800
```

### Example 3: Category-Specific Commission
```python
# Product in "Fine Bites" category with 15% commission
product = Product.objects.get(id=fine_bites_product_id)

print(f"Vendor Price: ₦{product.price}")
# Output: Vendor Price: ₦5,000

print(f"Commission Rate: {product.get_commission_rate()}%")
# Output: Commission Rate: 15.0%

print(f"Commission: ₦{product.calculate_commission()}")
# Output: Commission: ₦750

print(f"Customer Pays: ₦{product.get_display_price()}")
# Output: Customer Pays: ₦5,750
```

---

## Order Processing Examples

### Calculate Earnings Split
```python
from product.models import Product

product = Product.objects.get(id=product_id)
quantity = 3

# What vendor receives
vendor_earnings = product.get_vendor_earnings(quantity)
print(f"Vendor Receives: ₦{vendor_earnings}")
# Output: Vendor Receives: ₦30,000 (₦10,000 × 3)

# What platform receives
platform_earnings = product.get_platform_earnings(quantity)
print(f"Platform Receives: ₦{platform_earnings}")
# Output: Platform Receives: ₦3,000 (₦1,000 × 3)

# Total customer payment
total_paid = product.get_display_price() * quantity
print(f"Customer Paid: ₦{total_paid}")
# Output: Customer Paid: ₦33,000
```

### Product Variant Pricing
```python
# For variant products (products with parent)
variant = Product.objects.get(parent__isnull=False, id=variant_id)

# Variants inherit commission from vendor
print(f"Variant Commission Rate: {variant.get_commission_rate()}%")
print(f"Variant Display Price: ₦{variant.get_display_price()}")
```

---

## API Response Format

### ProductSerializer Should Return:
```json
{
    "id": "uuid-here",
    "name": "Delicious Meal",
    "price": 10000.00,              // Original vendor price
    "display_price": 11000.00,       // What customer pays
    "commission_rate": 10.00,        // Percentage
    "commission_amount": 1000.00,    // Actual commission
    "discounted_price": 8000.00,     // If discount active
    // ... other fields
}
```

---

## Admin Dashboard - Vendor Earnings View

```python
# Calculate vendor's total earnings for a period
from product.models import Order, OrderItem
from django.db.models import Sum, F

vendor = Vendor.objects.get(id=vendor_id)

# Get all completed orders
orders = Order.objects.filter(
    vendor=vendor,
    status='delivered',
    created_at__gte=start_date,
    created_at__lte=end_date
)

total_sales = 0
total_commission = 0

for order in orders:
    for item in order.items.all():
        product = item.product
        quantity = item.quantity
        
        # Vendor earnings (before commission)
        vendor_amount = product.get_vendor_earnings(quantity)
        
        # Platform commission
        commission = product.get_platform_earnings(quantity)
        
        total_sales += vendor_amount
        total_commission += commission

print(f"Vendor Earnings: ₦{total_sales}")
print(f"Platform Commission: ₦{total_commission}")
print(f"Total Order Value: ₦{total_sales + total_commission}")
```

---

## Commission Priority Examples

### Scenario 1: Vendor-specific overrides everything
```python
# Platform default: 10%
# Category (Fine Bites): 15%
# Vendor: 8%

vendor.commission_percentage = 8.00
product.get_commission_rate()  # Returns: 8.0% (vendor wins)
```

### Scenario 2: Category-specific (no vendor override)
```python
# Platform default: 10%
# Category (Fine Bites): 15%
# Vendor: None

vendor.commission_percentage = None
product.get_commission_rate()  # Returns: 15.0% (category wins)
```

### Scenario 3: Platform default
```python
# Platform default: 10%
# Category: None
# Vendor: None

vendor.commission_percentage = None
category.commission_percentage = None
product.get_commission_rate()  # Returns: 10.0% (platform default)
```

---

## Disabling Commission Globally

```python
# Temporarily disable commission calculations
settings = PlatformSettings.get_settings()
settings.is_commission_active = False
settings.save()

# Now all products return 0% commission
product.calculate_commission()  # Returns: 0.00
product.get_display_price()     # Returns: same as product.price
```

---

## Testing Commands

```bash
# Create platform settings
python manage.py shell
>>> from product.models import PlatformSettings
>>> settings = PlatformSettings.get_settings()
>>> print(settings)

# Test commission calculation
>>> from product.models import Product
>>> p = Product.objects.first()
>>> print(f"Rate: {p.get_commission_rate()}%")
>>> print(f"Commission: ₦{p.calculate_commission()}")
>>> print(f"Display Price: ₦{p.get_display_price()}")
```

---

## Important Notes

1. **Commission applies AFTER tax** (as per requirements)
2. **Commission does NOT apply to delivery fees** (only product prices)
3. **Variants inherit** commission rate from their vendor
4. **Discounts are calculated first**, then commission is added to discounted price
5. **Admin can change** commission at any level via Django admin interface
