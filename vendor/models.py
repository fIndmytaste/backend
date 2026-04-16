import uuid
from django.db import models

# Create your models here.


class MarketPlace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(null=True,blank=True)
    is_active = models.BooleanField(default=True)
    
    # Delivery pricing settings
    delivery_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=1000.00, 
        help_text="Base delivery fee for first item"
    )
    second_item_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=1000.00,
        help_text="Fee for second item (standard categories)"
    )
    additional_item_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=200.00,
        help_text="Fee per item from 3rd onwards (standard categories)"
    )
    special_category_discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=50.00,
        help_text="Discount % for additional items in special categories"
    )
    
    has_perishables = models.BooleanField(default=False, help_text="Indicates if the marketplace deals with perishable goods.") 
    created_at = models.DateTimeField(auto_now_add=True)
    vendors = models.ManyToManyField('account.Vendor')
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.name
