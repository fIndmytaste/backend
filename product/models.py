import uuid
import string
import random
from django.db import models
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()  


def generate_track_id(length=8):
    """Generate a random alphanumeric string for track_id."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# System Category model
class SystemCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="The name of the system category.")
    description = models.TextField(help_text="A detailed description of the system category.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the category was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the category was last updated.")

    def __str__(self):
        return self.name


# Vendor Category model
class VendorCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="The name of the vendor category.")
    description = models.TextField(help_text="A detailed description of the vendor category.")
    vendor = models.ForeignKey('account.Vendor', on_delete=models.CASCADE, help_text="The vendor associated with this category.")
    is_active = models.BooleanField(default=True, help_text="Indicates whether this vendor category is active or not.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the category was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the category was last updated.")

    def __str__(self):
        return self.name


# Product model
class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="The name of the product.")
    description = models.TextField(help_text="A detailed description of the product.")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="The regular price of the product.")
    system_category = models.ForeignKey('SystemCategory', on_delete=models.CASCADE, null=True,blank=True, help_text="The system category to which this product belongs.")
    category = models.ForeignKey('VendorCategory', on_delete=models.CASCADE,null=True,blank=True, help_text="The vendor category of this product.")
    image = models.ImageField(upload_to='products/', blank=True, null=True, help_text="An image of the product.")
    stock = models.IntegerField(default=0, help_text="The number of units available in stock.")
    is_active = models.BooleanField(default=True, help_text="Indicates whether the product is active and available for sale.")
    is_delete = models.BooleanField(default=False, help_text="Indicates whether the product is marked for deletion.")
    is_featured = models.BooleanField(default=False, help_text="Indicates whether the product is marked for featured.")
    vendor = models.ForeignKey('account.Vendor', on_delete=models.CASCADE, help_text="The vendor selling this product.")

    apply_discount = models.BooleanField(default=False, help_text="Indicates whether a discount is applied to this product.")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="The discount percentage on this product (e.g., 20 for 20%).")
    discount_start_date = models.DateTimeField(null=True, blank=True, help_text="The start date of the discount.")
    discount_end_date = models.DateTimeField(null=True, blank=True, help_text="The end date of the discount.")

    views = models.PositiveIntegerField(default=0)  # Track views
    purchases = models.PositiveIntegerField(default=0)  # Track purchases
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the product was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the product was last updated.")

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


    def is_favorite(self):
        """
        Returns True if the product is in the user's favorites, otherwise False.
        """
        return Favorite.objects.filter(user=self.user, product=self.product).exists()

 

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



class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="product_images", help_text="Product image")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the product image was")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the product image was last")
    is_primary = models.BooleanField(default=False, help_text="Is this the primary image for the product")
    is_active = models.BooleanField(default=True, help_text="Is this image active")


class Order(models.Model):
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    PAYMENT_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PAID, 'Paid'),
        (FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,blank=True, related_name='orders', help_text="The user who placed the order.")
    vendor = models.ForeignKey('account.Vendor', on_delete=models.SET_NULL,null=True,blank=True, related_name='vendors', help_text="The vendor who owns the order.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the order was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the order was last updated.")
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('shipped', 'Shipped'), ('canceled', 'Canceled'), ('delivered', 'Delivered')], default='pending', help_text="The current status of the order.")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="The total amount of the order.")
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PENDING,
        help_text="The payment status of the order."
    )

    track_id = models.CharField(max_length=100, help_text="Unique tracking ID per user")

    def __str__(self):
        return f"Order #{self.id}"

    def update_total_amount(self):
        """Recalculates the total order amount based on order items."""
        total = sum(item.total_price() for item in self.items.all())
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

        super().save(*args, **kwargs)


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', help_text="The order to which this item belongs.")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, help_text="The product in this order item.")
    quantity = models.PositiveIntegerField(default=1, help_text="The quantity of the product in the order.")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price of the product at the time of the order.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def total_price(self):
        """Returns the total price for this item (price * quantity)."""
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"


class Rating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.DecimalField(max_digits=2, decimal_places=1)  # e.g., 4.5 out of 5
    comment = models.TextField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')  # Ensures each user can rate a product only once

    def __str__(self):
        return f"Rating for {self.product.name} by {self.user.username}"


class Favorite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'product']  # A user can only favorite a product once

    def __str__(self):
        return f"{self.user} - {self.product.name}"

class ProductView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'product')  # Ensure that each user can view the product only once
