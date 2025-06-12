import uuid
import string
import random
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model
from django.db import transaction
from cloudinary.models import CloudinaryField



User = get_user_model()




def generate_track_id(length=8):
    """Generate a random alphanumeric string for track_id."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# System Category model
class SystemCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="The name of the system category.")
    logo = CloudinaryField('profile_images', null=True, blank=True)
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
    # image = models.ImageField(upload_to='products/', blank=True, null=True, help_text="An image of the product.")
    stock = models.IntegerField(default=0, help_text="The number of units available in stock.")
    is_active = models.BooleanField(default=True, help_text="Indicates whether the product is active and available for sale.")
    is_delete = models.BooleanField(default=False, help_text="Indicates whether the product is marked for deletion.")
    is_featured = models.BooleanField(default=False, help_text="Indicates whether the product is marked for featured.")
    vendor = models.ForeignKey('account.Vendor', on_delete=models.CASCADE, help_text="The vendor selling this product.")

    starting_delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500.00,
        help_text="The starting delivery fee for this product.",
    )
    apply_discount = models.BooleanField(default=False, help_text="Indicates whether a discount is applied to this product.")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="The discount percentage on this product (e.g., 20 for 20%).")
    discount_start_date = models.DateTimeField(null=True, blank=True, help_text="The start date of the discount.")
    discount_end_date = models.DateTimeField(null=True, blank=True, help_text="The end date of the discount.")

    views = models.PositiveIntegerField(default=0)  # Track views
    purchases = models.PositiveIntegerField(default=0)  # Track purchases
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the product was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the product was last updated.")

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='variants',
        help_text="If this product is a variant, this points to the main product."
    )

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
    # image = models.ImageField(upload_to="product_images", help_text="Product image")
    image = CloudinaryField('product_images', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the product image was")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the product image was last")
    is_primary = models.BooleanField(default=False, help_text="Is this the primary image for the product")
    is_active = models.BooleanField(default=True, help_text="Is this image active")


    def get_image_url(self):
        if self.image:
            return self.image.url
        return None

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
        ('ready_for_pickup', 'Ready for Pickup'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('near_delivery', 'Near Delivery Location'),
        ('delivered', 'Delivered'),
        ('canceled', 'Canceled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', help_text="The user who placed the order.")
    vendor = models.ForeignKey('account.Vendor', on_delete=models.SET_NULL, null=True, blank=True, related_name='vendors', help_text="The vendor who owns the order.")
    
    # Add the rider relationship
    rider = models.ForeignKey('account.Rider', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', help_text="The rider assigned to deliver this order.")
    
    country = models.CharField(max_length=64, null=True, blank=True)
    state = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)
    address = models.CharField(max_length=256, null=True, blank=True)
    location_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the order was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the order was last updated.")
    
    # Update status choices
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending', help_text="The current status of the order.")
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="The total amount of the order.")
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PENDING,
        help_text="The payment status of the order."
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default='pending',
        help_text="The delivery status of the order."
    )

    track_id = models.CharField(max_length=100, help_text="Unique tracking ID per user")
    
    # Add estimated delivery time fields
    estimated_pickup_time = models.DateTimeField(null=True, blank=True, help_text="Estimated time when the rider will pick up the order.")
    estimated_delivery_time = models.DateTimeField(null=True, blank=True, help_text="Estimated time when the order will be delivered.")
    
    # Add actual delivery time fields for metrics
    actual_pickup_time = models.DateTimeField(null=True, blank=True, help_text="Actual time when the rider picked up the order.")
    actual_delivery_time = models.DateTimeField(null=True, blank=True, help_text="Actual time when the order was delivered.")

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
    
    def assign_rider(self, rider):
        """Assign a rider to this order and update status."""
        self.rider = rider
        self.status = 'confirmed'
        self.save()
        # Create a delivery tracking entry when a rider is assigned
        DeliveryTracking.objects.create(order=self)
        
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



class DeliveryTracking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='delivery_tracking')
    
    # Rider's current location during delivery
    rider_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rider_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
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
        rider_lat, rider_lng, dest_lat, dest_lng = map(radians, [rider_lat, rider_lng, dest_lat, dest_lng])
        
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
        
        speed = speeds.get(rider.mode_of_transport, 333)  # Default to bike speed
        
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
