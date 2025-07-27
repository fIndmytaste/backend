from math import radians, sin, cos, sqrt, atan2

def get_distance_between_two_location(lat1, lon1, lat2, lon2):
    print(lat1,lon1,lat2,lon2)
    try:
        # Validate input types
        for value in [lat1, lon1, lat2, lon2]:
            print(lat1)
            print(type(lat1))
            print(isinstance(value, (int, float)))
            if not isinstance(value, (int, float)):
                raise TypeError("Latitude and longitude must be numeric values.")

        # Validate latitude and longitude ranges
        if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
            raise ValueError("Longitude must be between -180 and 180 degrees.")

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        R = 6371  # Earth's radius in kilometers

        return R * c

    except Exception as e:
        print(f"Error calculating distance: {e}")
        return None



def calculate_delivery_fee(distance_km, item_count):
    base_rate = 2.0
    per_km_rate = 0.5  
    per_item_rate = 0.2 

    return round(base_rate + (per_km_rate * distance_km) + (per_item_rate * item_count), 2)
