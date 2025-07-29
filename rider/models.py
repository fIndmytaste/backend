import math, uuid
from django.db import models
from django.utils import timezone
# Create your models here.



class DeliveryTracking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('product.Order', related_name='delivery_tracking', on_delete=models.CASCADE)
    rider_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rider_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    distance_to_customer = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)  # in KM
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def update_rider_location(self, latitude, longitude):
        self.rider_latitude = latitude
        self.rider_longitude = longitude
        
        # Calculate distance to customer
        if self.order.delivery_latitude and self.order.delivery_longitude:
            self.distance_to_customer = self.calculate_distance(
                float(latitude), float(longitude),
                float(self.order.delivery_latitude),
                float(self.order.delivery_longitude)
            )
            
            # Update ETA
            self.estimated_delivery_time = self.calculate_eta()
        
        self.save()
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance in kilometers"""
        R = 6371
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def calculate_eta(self):
        if not self.distance_to_customer:
            return None
        
        # Assume 25 km/h average speed
        hours = float(self.distance_to_customer) / 25
        return timezone.now() + timedelta(hours=hours)
    
    def is_near_delivery_location(self, threshold_km=0.5):
        """Check if rider is within threshold distance of delivery location"""
        return self.distance_to_customer and self.distance_to_customer <= threshold_km

