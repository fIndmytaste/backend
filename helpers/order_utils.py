# from math import radians, sin, cos, sqrt, atan2

# def get_distance_between_two_location(lat1, lon1, lat2, lon2):
#     print(lat1,lon1, " :::: ",lat2,lon2)
#     try:
#         # Validate input types
#         for value in [lat1, lon1, lat2, lon2]:
#             if not isinstance(value, (int, float)):
#                 raise TypeError("Latitude and longitude must be numeric values.")

#         # Validate latitude and longitude ranges
#         if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
#             raise ValueError("Latitude must be between -90 and 90 degrees.")
#         if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
#             raise ValueError("Longitude must be between -180 and 180 degrees.")

#         # Convert to radians
#         lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

#         # Haversine formula
#         dlat = lat2 - lat1
#         dlon = lon2 - lon1

#         a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
#         c = 2 * atan2(sqrt(a), sqrt(1 - a))
#         R = 6371  # Earth's radius in kilometers

#         return R * c

#     except Exception as e:
#         print(f"Error calculating distance: {e}")
#         return None



# def calculate_delivery_fee(distance_km, item_count = 5):
#     print("Distance ", distance_km)
#     if distance_km <= 0:
#         distance_km =  1

#     base_rate = 1000
#     per_km_rate = 1.5  
#     per_item_rate = 0.2 

#     print(per_km_rate * distance_km)

#     return round(base_rate * (per_km_rate * distance_km) + (per_item_rate * item_count), 2)


from math import radians, sin, cos, sqrt, atan2

# -------------------------
# 1. Distance Calculation
# -------------------------
def get_distance_between_two_location(lat1, lon1, lat2, lon2):
    """Returns distance in kilometers between two GPS coordinates."""
    try:
        for value in [lat1, lon1, lat2, lon2]:
            if not isinstance(value, (int, float)):
                raise TypeError("Latitude and longitude must be numeric values.")
        if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
            raise ValueError("Longitude must be between -180 and 180 degrees.")

        R = 6371  # Earth radius in km
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c
    except Exception as e:
        print(f"Error calculating distance: {e}")
        return None


# -------------------------
# 2. Base Fee Calculation
# -------------------------
def get_base_fee(distance_km):
    """Determines base fee using tiered + smooth scaling."""
    if distance_km <= 2:
        base_fee = 1000
    elif distance_km <= 5:
        base_fee = 1200
    elif distance_km <= 10:
        base_fee = 1500
    else:
        base_fee = 2000

    # Smooth growth rate for each km beyond 2 km
    growth_rate = 30
    base_fee += max(0, (distance_km - 2)) * growth_rate
    return base_fee


# -------------------------
# 3. Surge & Surcharge
# -------------------------
def apply_surge(base_fee, traffic_level=1.0, weather_factor=1.0, rider_availability=1.0):
    """Adjusts fee for traffic, weather, and rider availability."""
    surge_factor = traffic_level * weather_factor * rider_availability
    return round(base_fee * surge_factor, 2)


def calculate_delivery_fee(distance_km, item_count=1, traffic_level=1.0, weather_factor=1.0, rider_availability=1.0):
    """Main delivery fee calculation."""
    if distance_km <= 0:
        distance_km = 1

    base_fee = get_base_fee(distance_km)
    surged_fee = apply_surge(base_fee, traffic_level, weather_factor, rider_availability)

    item_surcharge = 50 * (item_count - 1) if item_count > 1 else 0
    total_fee = surged_fee + item_surcharge

    return {
        "distance_km": round(distance_km, 2),
        "base_fee": round(base_fee, 2),
        "surged_fee": surged_fee,
        "total_delivery_fee": round(total_fee, 2)
    }


# -------------------------
# 4. Vendor Delivery Price from Coordinates
# -------------------------
def calculate_fee_from_coords(lat1, lon1, lat2, lon2, item_count=1, traffic_level=1.0, weather_factor=1.0, rider_availability=1.0):
    distance_km = get_distance_between_two_location(lat1, lon1, lat2, lon2)
    if distance_km is None:
        return None
    return calculate_delivery_fee(distance_km, item_count, traffic_level, weather_factor, rider_availability)


# # -------------------------
# # Example Usage
# # -------------------------
# if __name__ == "__main__":
#     vendor_lat, vendor_lon = 6.6751345, 3.3301271
#     customer_lat, customer_lon = 6.6852000, 3.3405000

#     result = calculate_fee_from_coords(
#         vendor_lat, vendor_lon,
#         customer_lat, customer_lon,
#         item_count=3,
#         traffic_level=1.2,   # Heavy traffic
#         weather_factor=1.3,  # Rain
#         rider_availability=1.1  # Slight shortage of riders
#     )

#     print(result)
