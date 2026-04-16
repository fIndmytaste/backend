import uuid
import random
from decimal import Decimal
from django.contrib.auth import get_user_model
from product.models import Order, DeliveryTracking
from account.models import Vendor
import traceback

User = get_user_model()

def run_test():
    uid = str(uuid.uuid4())[:8]
    email = f"test_{uid}@example.com"
    username = f"test_{uid}"
    
    with open("verification_output.txt", "w") as f:
        def log(msg):
            print(msg)
            f.write(str(msg) + "\n")

        log(f"Starting Verification with ID: {uid}")

        try:
            # Create Users
            user = User.objects.create_user(email=email, password="password")
            vendor_user = User.objects.create_user(email=f"v_{uid}@example.com", password="password")
            
            # Create Vendor
            # Vendor location: (0, 0)
            vendor = Vendor.objects.create(
                user=vendor_user,
                name=f"Test Vendor {uid}",
                location_latitude=Decimal('0.000000'),
                location_longitude=Decimal('0.000000'),
                address="Test Address"
            )
            
            # Create Order
            # Delivery location: Lat 0.1, Lon 0.0
            # Distance approx 11,119 meters (11.12 km)
            # Expected Time @ 333m/min ~ 33.39 mins -> 33
            order = Order.objects.create(
                user=user,
                vendor=vendor,
                status='pending',
                total_amount=Decimal('100.00'),
                location_latitude=Decimal('0.100000'),
                location_longitude=Decimal('0.000000'),
                delivery_latitude=Decimal('0.100000'),
                delivery_longitude=Decimal('0.000000')
            )
            
            log(f"Created Order {order.id}")
            
            # Test 1: Pending (Vendor -> Customer)
            est_1 = order.get_estimated_delivery_duration()
            log(f"Test 1 (Pending, Vendor->Cust): {est_1} mins")
            
            if est_1 is not None and 32 <= est_1 <= 35:
                log("✅ Test 1 Passed")
            else:
                log(f"❌ Test 1 Failed: Expected ~33, got {est_1}")

            # Test 2: Active (Picked Up) but No Tracking -> Fallback to Vendor
            order.status = 'picked_up'
            order.save()
            
            est_2 = order.get_estimated_delivery_duration()
            log(f"Test 2 (Picked Up, No Tracking): {est_2} mins")
            
            if est_2 == est_1:
                 log("✅ Test 2 Passed (Fallback worked)")
            else:
                 log(f"❌ Test 2 Failed: Expected {est_1}, got {est_2}")

            # Test 3: Active (Picked Up) with Tracking (Rider -> Customer)
            # Rider location: Lat 0.05, Lon 0.0
            # Distance approx 5,559 meters (5.56 km)
            # Expected Time @ 333m/min ~ 16.69 mins -> 16
            DeliveryTracking.objects.create(
                order=order,
                rider_latitude=Decimal('0.050000'),
                rider_longitude=Decimal('0.000000')
            )
            
            est_3 = order.get_estimated_delivery_duration()
            log(f"Test 3 (Picked Up, With Tracking): {est_3} mins")
            
            if est_3 is not None and 15 <= est_3 <= 18:
                log("✅ Test 3 Passed")
            else:
                log(f"❌ Test 3 Failed: Expected ~16, got {est_3}")

        except Exception as e:
            log(f"Error: {e}")
            traceback.print_exc(file=f)


run_test()
