from geopy.distance import geodesic

# 📍 Coordinates
vendor_location = (6.6751345, 3.3301271)          # Maria Cooks
customer_location = (6.674527299999999, 3.3309627)

kwara_location = (8.9848, 4.562443)               # Kwara State approx center
ogun_location = (6.9098333, 3.2583626)            # Ogun State approx center

# 🧮 Calculate distances
distance_vendor_to_kwara = geodesic(vendor_location, kwara_location).kilometers
distance_customer_to_kwara = geodesic(customer_location, kwara_location).kilometers

distance_vendor_to_ogun = geodesic(vendor_location, ogun_location).kilometers
distance_customer_to_ogun = geodesic(customer_location, ogun_location).kilometers

# 🖨️ Print results
print(f"Distance from Vendor to Kwara: {distance_vendor_to_kwara:.2f} km")
print(f"Distance from Customer to Kwara: {distance_customer_to_kwara:.2f} km")
print(f"Distance from Vendor to Ogun: {distance_vendor_to_ogun:.2f} km")
print(f"Distance from Customer to Ogun: {distance_customer_to_ogun:.2f} km")
