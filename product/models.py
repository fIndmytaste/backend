import uuid
from django.db import models



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
    system_category = models.ForeignKey('SystemCategory', on_delete=models.CASCADE, help_text="The system category to which this product belongs.")
    category = models.ForeignKey('VendorCategory', on_delete=models.CASCADE, help_text="The vendor category of this product.")
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


# Favorite model
class Favorite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('account.User', on_delete=models.CASCADE, help_text="The user who favorited the product.")
    product = models.ForeignKey('Product', on_delete=models.CASCADE, help_text="The product that is favorited.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the product was added to the user's favorites.")

    class Meta:
        unique_together = ['user', 'product']  # Ensure a user can only favorite a product once

    def __str__(self):
        return f"{self.user.email} - {self.product.name} (Favorite)"

    def is_favorite(self):
        """
        Returns True if the product is in the user's favorites, otherwise False.
        """
        return Favorite.objects.filter(user=self.user, product=self.product).exists()
