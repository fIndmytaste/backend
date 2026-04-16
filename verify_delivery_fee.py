import os
import django
import sys
from decimal import Decimal

# Setup Django environment
sys.path.append('/Users/olakay/Desktop/dev/personal/findmytaste')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'findmytaste.settings')
django.setup()

from helpers.order_utils import calculate_delivery_fee, DeliveryConfig

def test_delivery_calculation():
    print("--- Starting Delivery Fee Optimization Verification ---")
    
    # Test Case 1: Standard Order (Short Distance, No Surge)
    print("\n[Test 1] Standard Order (Short Distance, 1.5km)")
    result = calculate_delivery_fee(
        origin_lat=6.45, origin_lon=3.40,
        dest_lat=6.46, dest_lon=3.41,
        order_value=5000,
        item_count=1,
        weight_kg=1.0
    )
    
    if result['success']:
        print(f"✅ Success: Calculation ID {result['calculation_id']}")
        print(f"Base Fee: ₦{result['breakdown']['base_fee']}")
        print(f"Service Fee: ₦{result['breakdown']['service_fee']} (Expected: {5000 * 0.025})")
        print(f"Delivery Fee: ₦{result['delivery_fee']}")
        print(f"Total Fee (Cust Pays): ₦{result['total_fee']}")
    else:
        print(f"❌ Failed: {result.get('error')}")

    # Test Case 2: High Value Order (Capped Service Fee)
    print("\n[Test 2] High Value Order (Capped Service Fee)")
    result = calculate_delivery_fee(
        origin_lat=6.45, origin_lon=3.40,
        dest_lat=6.46, dest_lon=3.41,
        order_value=50000, # 2.5% is 1250, should be capped at 500
        item_count=1,
        weight_kg=1.0
    )
    
    if result['success']:
        print(f"Service Fee: ₦{result['breakdown']['service_fee']} (Expected: 500.0)")
        if result['breakdown']['service_fee'] == 500.0:
            print("✅ Service Fee correctly capped")
        else:
             print("❌ Service Fee NOT capped correctly")
    else:
        print(f"❌ Failed: {result.get('error')}")

    # Test Case 3: Long Distance & Surge (Simulated)
    print("\n[Test 3] Long Distance & Surge (15km)")
    # Using larger coordinate spread for ~15km
    result = calculate_delivery_fee(
        origin_lat=6.45, origin_lon=3.40,
        dest_lat=6.55, dest_lon=3.50,
        order_value=10000,
        item_count=1,
        weight_kg=1.0
    )
    
    if result['success']:
        print(f"Distance: {result['route']['distance_km']:.2f} km")
        print(f"Base Fee: ₦{result['breakdown']['base_fee']}")
        print(f"Surge Amount: ₦{result['breakdown']['surge_amount']}")
        print(f"Final Delivery Fee: ₦{result['delivery_fee']}")
        print(f"Grand Total: ₦{result['total_fee']}")
        print("✅ Long distance calculation completed")
    else:
        print(f"❌ Failed: {result.get('error')}")

    print("\n--- Verification Completed ---")

if __name__ == "__main__":
    test_delivery_calculation()
