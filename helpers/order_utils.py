
"""
Enhanced Delivery Fee Calculation System
========================================

This module provides comprehensive delivery fee calculation with:
- Configurable pricing tiers and time-based pricing
- Real-time traffic, weather, and rider availability integration
- Peak hours pricing and vendor-specific fees
- Customer loyalty discounts and delivery time estimation
- Robust error handling and caching optimization
"""

import hashlib
from math import radians, sin, cos, sqrt, atan2
import random
import requests
import logging
from datetime import datetime, time
from typing import Dict, Optional, Tuple, Any
from django.core.cache import cache
from django.conf import settings


# Configure logging
logger = logging.getLogger(__name__)

# Import configuration manager (with fallback for when models aren't available)
try:
    from helpers.models import ConfigurationManager
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False


def get_route_cache_key(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                        precision: int = 4) -> str:
    """
    Generate a cache key for route calculations with coordinate precision.

    Args:
        origin_lat: Origin latitude
        origin_lon: Origin longitude  
        dest_lat: Destination latitude
        dest_lon: Destination longitude
        precision: Decimal places for coordinate rounding (default: 4)

    Returns:
        Cache key string
    """
    # Round coordinates to reduce cache key variations for nearby locations
    orig_lat = round(origin_lat, precision)
    orig_lon = round(origin_lon, precision)
    dest_lat_rounded = round(dest_lat, precision)
    dest_lon_rounded = round(dest_lon, precision)

    return f"route_{orig_lat}_{orig_lon}_{dest_lat_rounded}_{dest_lon_rounded}"


def get_cached_route_data(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached route data including distance and base calculations.

    Returns:
        Cached route data or None if not found
    """
    cache_key = get_route_cache_key(origin_lat, origin_lon, dest_lat, dest_lon)
    try:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Route cache hit for key: {cache_key}")
            return cached_data
        else:
            logger.debug(f"Route cache miss for key: {cache_key}")
            return None
    except Exception as e:
        logger.warning(
            f"Error retrieving route cache for key {cache_key}: {e}")
        return None


def cache_route_data(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                     route_data: Dict[str, Any]) -> None:
    """
    Cache route data for future use.

    Args:
        origin_lat: Origin latitude
        origin_lon: Origin longitude
        dest_lat: Destination latitude  
        dest_lon: Destination longitude
        route_data: Route data to cache
    """
    cache_key = get_route_cache_key(origin_lat, origin_lon, dest_lat, dest_lon)
    try:
        # Add timestamp to cached data
        route_data['cached_at'] = datetime.now().isoformat()
        cache.set(cache_key, route_data, DeliveryConfig.ROUTE_CACHE_TIMEOUT)
        logger.debug(f"Route data cached with key: {cache_key}")
    except Exception as e:
        logger.warning(f"Error caching route data for key {cache_key}: {e}")


def get_api_cache_key(api_name: str, params: Dict[str, Any]) -> str:
    """
    Generate a cache key for API calls.

    Args:
        api_name: Name of the API (e.g., 'google_maps', 'openweather')
        params: Parameters used in the API call

    Returns:
        Cache key string
    """
    import hashlib
    # Sort params for consistent key generation
    sorted_params = sorted(params.items())
    params_str = "&".join([f"{k}={v}" for k, v in sorted_params])
    return f"api_cache:{api_name}:{hashlib.md5(params_str.encode()).hexdigest()}"


def cache_api_response(api_name: str, params: Dict[str, Any], response_data: Any, timeout: int) -> None:
    """
    Cache API response with metadata.

    Args:
        api_name: Name of the API
        params: Parameters used in the API call
        response_data: The API response data
        timeout: Cache timeout in seconds
    """
    import time
    cache_key = get_api_cache_key(api_name, params)
    cached_data = {
        'data': response_data,
        'timestamp': time.time(),
        'api_name': api_name,
        'params': params
    }
    cache.set(cache_key, cached_data, timeout)
    logger.debug(f"Cached {api_name} API response with key: {cache_key}")


def get_cached_api_response(api_name: str, params: Dict[str, Any]) -> Optional[Any]:
    """
    Retrieve cached API response.

    Args:
        api_name: Name of the API
        params: Parameters used in the API call

    Returns:
        Cached response data or None if not found/expired
    """
    cache_key = get_api_cache_key(api_name, params)
    cached_result = cache.get(cache_key)

    if cached_result:
        logger.debug(f"Cache hit for {api_name} API with key: {cache_key}")
        return cached_result['data']

    logger.debug(f"Cache miss for {api_name} API with key: {cache_key}")
    return None


# -------------------------
# Configuration System
# -------------------------
class DeliveryConfig:
    """
    Dynamic configuration for delivery fee calculation.
    Uses database configuration when available, falls back to hardcoded defaults.
    """

    # Fallback configurations (used when database is not available)
    _FALLBACK_CONFIG = {
        'base_pricing_tiers': [
            {"max_distance": 2, "base_fee": 1000, "per_km_rate": 50},
            {"max_distance": 5, "base_fee": 1200, "per_km_rate": 80},
            {"max_distance": 10, "base_fee": 1500, "per_km_rate": 100},
            {"max_distance": 20, "base_fee": 2000, "per_km_rate": 120},
            {"max_distance": float('inf'), "base_fee": 2500,
             "per_km_rate": 150}
        ],
        'peak_hours': [
            {"start": "07:00", "end": "09:30",
                "multiplier": 1.3, "name": "Morning Rush"},
            {"start": "12:00", "end": "14:00",
                "multiplier": 1.2, "name": "Lunch Rush"},
            {"start": "17:00", "end": "20:00",
                "multiplier": 1.4, "name": "Evening Rush"},
            {"start": "22:00", "end": "23:59",
                "multiplier": 1.2, "name": "Late Night"}
        ],
        'traffic_multipliers': {
            "free_flow": 1.0, "light": 1.1, "moderate": 1.3, "heavy": 1.6, "severe": 2.0
        },
        'weather_multipliers': {
            "clear": 1.0, "cloudy": 1.0, "light_rain": 1.2, "heavy_rain": 1.5,
            "thunderstorm": 1.8, "fog": 1.3, "snow": 2.0
        },
        'rider_availability_multipliers': {
            "high": 0.9, "normal": 1.0, "low": 1.3, "critical": 1.8
        },
        'vendor_type_multipliers': {
            "restaurant": 1.0, "grocery": 1.1, "pharmacy": 1.2, "electronics": 1.3, "fragile_items": 1.5
        },
        'loyalty_discounts': {
            "bronze": 0.05, "silver": 0.10, "gold": 0.15, "platinum": 0.20
        },
        'max_distance_km': 50,
        'min_delivery_fee': 500,
        'max_delivery_fee': 10000,
        'base_delivery_speed_kmh': 25,
        'preparation_time_minutes': 15,
        'max_surge_multiplier': 3.0,
        'free_item_threshold': 1,
        'item_surcharge_per_item': 50.0,
        'free_weight_threshold_kg': 2.0,
        'weight_surcharge_per_kg': 100.0,
        'route_cache_timeout': 1800,
        'weather_cache_timeout': 600,
        'traffic_cache_timeout': 180,
        'rider_cache_timeout': 120,
        'service_fee_percentage': 2.5,
        'max_service_fee': 500.0,
    }

    @classmethod
    def get_config(cls, key: str, default=None):
        """Get configuration value with database fallback."""
        if CONFIG_MANAGER_AVAILABLE:
            try:
                return ConfigurationManager.get_config(key, cls._FALLBACK_CONFIG.get(key, default))
            except Exception as e:
                logger.warning(
                    f"Failed to get config from database for {key}: {e}")

        return cls._FALLBACK_CONFIG.get(key, default)

    @classmethod
    def _parse_time_string(cls, time_str: str) -> time:
        """Parse time string in HH:MM format to time object."""
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except:
            return time(0, 0)

    @property
    def BASE_FARE(self):
        return self.get_config('base_fare', 500.00)

    @property
    def INCREMENTAL_CHARGE(self):
        return self.get_config('incremental_charge', 200.00)

    @property
    def BASE_DISTANCE_RANGE(self):
        return self.get_config('base_distance_range', 1.2)

    @property
    def INCREMENTAL_DISTANCE(self):
        return self.get_config('incremental_distance', 0.5)

    @property
    def PLATFORM_OPERATIONAL_FEE(self):
        return self.get_config('platform_operational_fee', 100.00)

    @property
    def MAX_DELIVERY_DISTANCE(self):
        return self.get_config('max_delivery_distance', 10.0)

    @property
    def PREPARATION_TIME_MINUTES(self):
        return self.get_config('preparation_time_minutes', 15)

    @property
    def SERVICE_FEE_PERCENTAGE(self):
        return self.get_config('service_fee_percentage')

    @property
    def MAX_SERVICE_FEE(self):
        return self.get_config('max_service_fee')

    @property
    def MAX_SURGE_MULTIPLIER(self):
        return self.get_config('max_surge_multiplier')

    @property
    def FREE_ITEM_THRESHOLD(self):
        return self.get_config('free_item_threshold')

    @property
    def ITEM_SURCHARGE_PER_ITEM(self):
        return self.get_config('item_surcharge_per_item')

    @property
    def FREE_WEIGHT_THRESHOLD_KG(self):
        return self.get_config('free_weight_threshold_kg')

    @property
    def WEIGHT_SURCHARGE_PER_KG(self):
        return self.get_config('weight_surcharge_per_kg')

    @property
    def ROUTE_CACHE_TIMEOUT(self):
        return self.get_config('route_cache_timeout')

    @property
    def WEATHER_CACHE_TIMEOUT(self):
        return self.get_config('weather_cache_timeout')

    @property
    def TRAFFIC_CACHE_TIMEOUT(self):
        return self.get_config('traffic_cache_timeout')

    @property
    def RIDER_CACHE_TIMEOUT(self):
        return self.get_config('rider_cache_timeout')

    @property
    def MIN_DELIVERY_FEE(self):
        return self.get_config('min_delivery_fee')

    @property
    def MAX_DELIVERY_FEE(self):
        return self.get_config('max_delivery_fee')

    @property
    def BASE_PRICING_TIERS(self):
        return self.get_config('base_pricing_tiers')

    @property
    def PEAK_HOURS(self):
        return self.get_config('peak_hours')

    @property
    def TRAFFIC_MULTIPLIERS(self):
        return self.get_config('traffic_multipliers')

    @property
    def WEATHER_MULTIPLIERS(self):
        return self.get_config('weather_multipliers')

    @property
    def RIDER_AVAILABILITY_MULTIPLIERS(self):
        return self.get_config('rider_availability_multipliers')

    @property
    def VENDOR_TYPE_MULTIPLIERS(self):
        return self.get_config('vendor_type_multipliers')

    @property
    def LOYALTY_DISCOUNTS(self):
        return self.get_config('loyalty_discounts')

    @property
    def MAX_DISTANCE_KM(self):
        return self.get_config('max_distance_km')

    @property
    def BASE_DELIVERY_SPEED_KMH(self):
        return self.get_config('base_delivery_speed_kmh')

    @property
    def ITEM_SURCHARGE_PER_ITEM(self):
        return self.get_config('item_surcharge_per_item')

    # Legacy properties for backward compatibility
    CACHE_TIMEOUT = 300
    PEAK_HOUR_CACHE_TIMEOUT = 3600
    LONG_DISTANCE_THRESHOLD_KM = 15
    ITEM_SURCHARGE = 50  # Deprecated, use ITEM_SURCHARGE_PER_ITEM
    WEIGHT_TIERS = [  # Deprecated, weight calculation now uses per-kg pricing
        {"max_weight": 5, "surcharge": 0},
        {"max_weight": 15, "surcharge": 100},
        {"max_weight": 30, "surcharge": 300},
        {"max_weight": float('inf'), "surcharge": 500}
    ]


# Create a singleton instance for global use
DeliveryConfig = DeliveryConfig()

# -------------------------
# 1. Enhanced Distance Calculation
# -------------------------


def get_distance_between_two_location(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[float]:
    """
    Calculate distance between two GPS coordinates using Haversine formula.

    Args:
        lat1, lon1: Origin coordinates
        lat2, lon2: Destination coordinates

    Returns:
        Distance in kilometers or None if calculation fails
    """
    cache_key = f"distance_{lat1}_{lon1}_{lat2}_{lon2}"
    cached_distance = cache.get(cache_key)
    if cached_distance is not None:
        return cached_distance

    logger.info(
        f"Calculating distance from ({lat1}, {lon1}) to ({lat2}, {lon2})")
    print(f"Calculating distance from ({lat1}, {lon1}) to ({lat2}, {lon2})")

    try:
        # Validate input types and ranges
        coordinates = [lat1, lon1, lat2, lon2]
        for i, coord in enumerate(coordinates):
            if not isinstance(coord, (int, float)):
                raise TypeError(
                    f"Coordinate {i+1} must be numeric, got {type(coord)}")

        if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
            raise ValueError(f"Invalid latitude values: {lat1}, {lat2}")
        if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
            raise ValueError(f"Invalid longitude values: {lon1}, {lon2}")

        # Convert to radians
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, coordinates)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = 6371 * c  # Earth's radius in km

        # Cache the result
        cache.set(cache_key, distance, DeliveryConfig.ROUTE_CACHE_TIMEOUT)

        logger.info(f"Calculated distance: {distance:.2f} km")
        return round(distance, 2)

    except Exception as e:
        logger.error(f"Error calculating distance: {e}")
        return None


# -------------------------
# 2. Enhanced Base Fee Calculation
# -------------------------
def get_base_fee(distance_km: float, current_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate base delivery fee using configurable pricing tiers and time-based pricing.

    Args:
        distance_km: Distance in kilometers
        current_time: Current datetime for peak hour calculation

    Returns:
        Dictionary with base fee details
    """
    if distance_km <= 0:
        distance_km = 0.1  # Minimum distance

    # Find appropriate pricing tier
    tier = None
    for pricing_tier in DeliveryConfig.BASE_PRICING_TIERS:
        if distance_km <= pricing_tier["max_distance"]:
            tier = pricing_tier
            break

    if not tier:
        # Use highest tier as fallback
        tier = DeliveryConfig.BASE_PRICING_TIERS[-1]

    # Calculate base fee
    base_fee = tier["base_fee"]
    if distance_km > 2:  # Add per-km charges beyond 2km
        extra_distance = distance_km - 2
        base_fee += extra_distance * tier["per_km_rate"]

    # Apply time-based pricing
    peak_multiplier = 1.0
    peak_period = None

    if current_time is None:
        current_time = datetime.now()

    current_time_only = current_time.time()

    for peak in DeliveryConfig.PEAK_HOURS:
        peak_start = DeliveryConfig._parse_time_string(peak["start"])
        peak_end = DeliveryConfig._parse_time_string(peak["end"])
        if peak_start <= current_time_only <= peak_end:
            peak_multiplier = peak["multiplier"]
            peak_period = peak["name"]
            break

    time_adjusted_fee = base_fee * peak_multiplier

    return {
        "base_fee": round(base_fee, 2),
        "distance_km": round(distance_km, 2),
        "pricing_tier": tier,
        "peak_period": peak_period,
        "peak_multiplier": peak_multiplier,
        "time_adjusted_fee": round(time_adjusted_fee, 2)
    }


def get_peak_hour_info(current_time: Optional[datetime] = None) -> Dict[str, Any]:
    """Get current peak hour information"""
    if current_time is None:
        current_time = datetime.now()

    current_time_only = current_time.time()

    for peak in DeliveryConfig.PEAK_HOURS:
        peak_start = DeliveryConfig._parse_time_string(peak["start"])
        peak_end = DeliveryConfig._parse_time_string(peak["end"])
        if peak_start <= current_time_only <= peak_end:
            return {
                "is_peak": True,
                "period_name": peak["name"],
                "multiplier": peak["multiplier"],
                "start_time": peak["start"].strftime("%H:%M"),
                "end_time": peak["end"].strftime("%H:%M")
            }

    return {
        "is_peak": False,
        "period_name": "Regular Hours",
        "multiplier": 1.0,
        "start_time": None,
        "end_time": None
    }


# -------------------------
# 3. Enhanced Real-Time Factor Fetchers
# -------------------------
def fetch_traffic_level(origin: Tuple[float, float], destination: Tuple[float, float]) -> Dict[str, Any]:
    """
    Fetch real-time traffic information with fallback mechanisms.

    Args:
        origin: (lat, lon) tuple for origin
        destination: (lat, lon) tuple for destination

    Returns:
        Dictionary with traffic information and multiplier
    """
    cache_key = f"traffic_{origin[0]}_{origin[1]}_{destination[0]}_{destination[1]}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    try:
        # Try Google Maps Traffic API (replace with actual API key)
        if hasattr(settings, 'GOOGLE_MAPS_API_KEY') and settings.GOOGLE_MAPS_API_KEY:
            traffic_data = _fetch_google_traffic(origin, destination)
            if traffic_data:
                cache.set(cache_key, traffic_data,
                          DeliveryConfig.TRAFFIC_CACHE_TIMEOUT)
                return traffic_data

        # Fallback to simulated traffic based on time and location
        return _simulate_traffic_conditions(origin, destination)

    except Exception as e:
        logger.error(f"Error fetching traffic data: {e}")
        return _simulate_traffic_conditions(origin, destination)


def _fetch_google_traffic(origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[Dict[str, Any]]:
    """Fetch traffic data from Google Maps API with caching"""
    try:
        # Prepare API parameters for caching (exclude API key from cache key)
        cache_params = {
            'origin': f"{origin[0]},{origin[1]}",
            'destination': f"{destination[0]},{destination[1]}",
            'departure_time': 'now',
            'traffic_model': 'best_guess'
        }

        # Check cache first
        cached_response = get_cached_api_response(
            'google_maps_traffic', cache_params)
        if cached_response:
            return cached_response

        # Make API call
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = cache_params.copy()
        params['key'] = settings.GOOGLE_MAPS_API_KEY

        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if data['status'] == 'OK' and data['routes']:
            route = data['routes'][0]['legs'][0]
            duration = route['duration']['value']
            duration_in_traffic = route.get(
                'duration_in_traffic', {}).get('value', duration)

            traffic_ratio = duration / duration_in_traffic if duration_in_traffic > 0 else 1.0

            # Determine traffic level
            if traffic_ratio >= 0.9:
                level = "free_flow"
            elif traffic_ratio >= 0.7:
                level = "light"
            elif traffic_ratio >= 0.5:
                level = "moderate"
            elif traffic_ratio >= 0.3:
                level = "heavy"
            else:
                level = "severe"

            traffic_data = {
                "level": level,
                "multiplier": DeliveryConfig.TRAFFIC_MULTIPLIERS[level],
                "duration_seconds": duration,
                "duration_in_traffic_seconds": duration_in_traffic,
                "source": "google_maps"
            }

            # Cache the response
            cache_api_response('google_maps_traffic', cache_params,
                               traffic_data, DeliveryConfig.TRAFFIC_CACHE_TIMEOUT)
            return traffic_data

    except Exception as e:
        logger.warning(f"Google Maps API error: {e}")
        return None


def _simulate_traffic_conditions(origin: Tuple[float, float], destination: Tuple[float, float]) -> Dict[str, Any]:
    """Simulate traffic conditions based on time and location"""
    current_time = datetime.now().time()

    # Higher traffic during peak hours
    is_peak = any(
        peak["start"] <= current_time <= peak["end"]
        for peak in DeliveryConfig.PEAK_HOURS
    )

    if is_peak:
        levels = ["moderate", "heavy", "severe"]
        weights = [0.4, 0.4, 0.2]
    else:
        levels = ["free_flow", "light", "moderate"]
        weights = [0.5, 0.3, 0.2]

    level = random.choices(levels, weights=weights)[0]

    return {
        "level": level,
        "multiplier": DeliveryConfig.TRAFFIC_MULTIPLIERS[level],
        "source": "simulated",
        "is_peak_hour": is_peak
    }


def fetch_weather_factor(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch weather information with real API integration and fallbacks.

    Args:
        lat, lon: Coordinates for weather lookup

    Returns:
        Dictionary with weather information and multiplier
    """
    cache_key = f"weather_{lat}_{lon}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    try:
        # Try OpenWeatherMap API
        if hasattr(settings, 'OPENWEATHER_API_KEY') and settings.OPENWEATHER_API_KEY:
            weather_data = _fetch_openweather_data(lat, lon)
            if weather_data:
                cache.set(cache_key, weather_data,
                          DeliveryConfig.WEATHER_CACHE_TIMEOUT)
                return weather_data

        # Fallback to simulated weather
        return _simulate_weather_conditions()

    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return _simulate_weather_conditions()


def _fetch_openweather_data(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Fetch weather data from OpenWeatherMap API with caching"""
    try:
        # Prepare API parameters for caching (exclude API key from cache key)
        cache_params = {
            'lat': lat,
            'lon': lon,
            'units': 'metric'
        }

        # Check cache first
        cached_response = get_cached_api_response('openweather', cache_params)
        if cached_response:
            return cached_response

        # Make API call
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = cache_params.copy()
        params['appid'] = settings.OPENWEATHER_API_KEY

        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if response.status_code == 200:
            weather_main = data['weather'][0]['main'].lower()
            description = data['weather'][0]['description']

            # Map weather conditions to our categories
            condition_mapping = {
                'clear': 'clear',
                'clouds': 'cloudy',
                'rain': 'light_rain' if 'light' in description else 'heavy_rain',
                'drizzle': 'light_rain',
                'thunderstorm': 'thunderstorm',
                'snow': 'snow',
                'mist': 'fog',
                'fog': 'fog'
            }

            condition = condition_mapping.get(weather_main, 'clear')

            weather_data = {
                "condition": condition,
                "multiplier": DeliveryConfig.WEATHER_MULTIPLIERS[condition],
                "description": description,
                "temperature": data['main']['temp'],
                "source": "openweather"
            }

            # Cache the response
            cache_api_response('openweather', cache_params,
                               weather_data, DeliveryConfig.WEATHER_CACHE_TIMEOUT)
            return weather_data

    except Exception as e:
        logger.warning(f"OpenWeather API error: {e}")
        return None


def _simulate_weather_conditions() -> Dict[str, Any]:
    """Simulate weather conditions"""
    conditions = ['clear', 'cloudy', 'light_rain', 'heavy_rain']
    weights = [0.6, 0.2, 0.15, 0.05]  # Bias towards good weather

    condition = random.choices(conditions, weights=weights)[0]

    return {
        "condition": condition,
        "multiplier": DeliveryConfig.WEATHER_MULTIPLIERS[condition],
        "source": "simulated"
    }


def fetch_rider_availability() -> Dict[str, Any]:
    """
    Calculate rider availability with real data integration.

    Returns:
        Dictionary with rider availability information and multiplier
    """
    cache_key = "rider_availability"
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    try:
        # Try to get real rider data from database
        availability_data = _get_real_rider_availability()
        if availability_data:
            cache.set(cache_key, availability_data,
                      DeliveryConfig.RIDER_CACHE_TIMEOUT)
            return availability_data

        # Fallback to simulated data
        return _simulate_rider_availability()

    except Exception as e:
        logger.error(f"Error fetching rider availability: {e}")
        return _simulate_rider_availability()


def _get_real_rider_availability() -> Optional[Dict[str, Any]]:
    """Get real rider availability from database"""
    try:
        # This would integrate with your actual rider system
        # from rider.models import Rider
        # from order.models import Order

        # available_riders = Rider.objects.filter(is_active=True, is_available=True).count()
        # active_orders = Order.objects.filter(status__in=['pending', 'confirmed', 'in_transit']).count()

        # For now, return None to use simulation
        return None

    except Exception as e:
        logger.warning(f"Database rider availability error: {e}")
        return None


def _simulate_rider_availability() -> Dict[str, Any]:
    """Simulate rider availability based on time"""
    current_time = datetime.now().time()

    # Lower availability during peak hours
    is_peak = any(
        peak["start"] <= current_time <= peak["end"]
        for peak in DeliveryConfig.PEAK_HOURS
    )

    if is_peak:
        levels = ["low", "critical", "normal"]
        weights = [0.5, 0.3, 0.2]
    else:
        levels = ["high", "normal", "low"]
        weights = [0.4, 0.5, 0.1]

    level = random.choices(levels, weights=weights)[0]

    return {
        "level": level,
        "multiplier": DeliveryConfig.RIDER_AVAILABILITY_MULTIPLIERS[level],
        "source": "simulated",
        "is_peak_hour": is_peak
    }


# -------------------------
# 4. Advanced Features
# -------------------------
def calculate_vendor_specific_fee(vendor_id: str, base_fee: float) -> Dict[str, Any]:
    """
    Calculate vendor-specific delivery fee adjustments.

    Args:
        vendor_id: Unique identifier for the vendor
        base_fee: Base delivery fee before vendor adjustments

    Returns:
        Dictionary with vendor fee information
    """
    try:
        # This would integrate with your vendor model
        # from vendor.models import Vendor
        # vendor = Vendor.objects.get(id=vendor_id)

        # For now, simulate vendor-specific multipliers
        vendor_types = ['electronics', 'restaurant', 'grocery']
        vendor_type = random.choice(vendor_types)
        multiplier = DeliveryConfig.VENDOR_TYPE_MULTIPLIERS[vendor_type]

        adjusted_fee = base_fee * multiplier

        return {
            "vendor_type": vendor_type,
            "multiplier": multiplier,
            "original_fee": base_fee,
            "adjusted_fee": adjusted_fee,
            "adjustment": adjusted_fee - base_fee
        }

    except Exception as e:
        logger.error(f"Error calculating vendor-specific fee: {e}")
        return {
            "vendor_type": "standard",
            "multiplier": 1.0,
            "original_fee": base_fee,
            "adjusted_fee": base_fee,
            "adjustment": 0.0
        }


def calculate_loyalty_discount(customer_id: str, base_fee: float) -> Dict[str, Any]:
    """
    Calculate customer loyalty discount.

    Args:
        customer_id: Unique identifier for the customer
        base_fee: Base delivery fee before discount

    Returns:
        Dictionary with loyalty discount information
    """
    try:
        # This would integrate with your customer/loyalty system
        # from customer.models import Customer, LoyaltyProgram
        # customer = Customer.objects.get(id=customer_id)

        # Simulate customer loyalty level
        loyalty_levels = ['bronze', 'silver', 'gold', 'platinum']
        weights = [0.4, 0.3, 0.2, 0.1]  # Most customers are bronze
        loyalty_level = random.choices(loyalty_levels, weights=weights)[0]

        discount_percentage = DeliveryConfig.LOYALTY_DISCOUNTS[loyalty_level]
        discount_amount = base_fee * discount_percentage
        discounted_fee = base_fee - discount_amount

        return {
            "loyalty_level": loyalty_level,
            "discount_percentage": discount_percentage,
            "discount_amount": discount_amount,
            "original_fee": base_fee,
            "discounted_fee": discounted_fee
        }

    except Exception as e:
        logger.error(f"Error calculating loyalty discount: {e}")
        return {
            "loyalty_level": "bronze",
            "discount_percentage": 0.0,
            "discount_amount": 0.0,
            "original_fee": base_fee,
            "discounted_fee": base_fee
        }


def estimate_delivery_time(distance_km: float, traffic_data: Dict[str, Any], weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate delivery time based on distance, traffic, and weather conditions.

    Args:
        distance_km: Distance in kilometers
        traffic_data: Traffic information from fetch_traffic_level
        weather_data: Weather information from fetch_weather_factor

    Returns:
        Dictionary with delivery time estimation
    """
    try:
        # Base delivery time calculation (assuming average speed)
        base_speed_kmh = DeliveryConfig.BASE_DELIVERY_SPEED_KMH
        base_time_minutes = (distance_km / base_speed_kmh) * 60

        # Add preparation time
        preparation_time = DeliveryConfig.PREPARATION_TIME_MINUTES

        # Apply traffic factor
        traffic_multiplier = traffic_data.get('multiplier', 1.0)

        # Apply weather factor (affects delivery speed)
        weather_multiplier = weather_data.get('multiplier', 1.0)
        # Cap weather impact on speed
        weather_speed_factor = min(weather_multiplier, 1.5)

        # Calculate adjusted delivery time
        adjusted_time = (base_time_minutes * traffic_multiplier *
                         weather_speed_factor) + preparation_time

        # Add buffer time for reliability
        buffer_time = adjusted_time * 0.1  # 10% buffer
        total_time = adjusted_time + buffer_time

        # Round to nearest 5 minutes for user-friendly display
        estimated_time = round(total_time / 5) * 5

        return {
            "estimated_minutes": int(estimated_time),
            "base_time_minutes": int(base_time_minutes),
            "preparation_time_minutes": preparation_time,
            "traffic_delay_minutes": int((base_time_minutes * traffic_multiplier) - base_time_minutes),
            "weather_delay_minutes": int((base_time_minutes * weather_speed_factor) - base_time_minutes),
            "buffer_time_minutes": int(buffer_time),
            "distance_km": distance_km,
            "estimated_range": {
                "min_minutes": int(estimated_time * 0.9),
                "max_minutes": int(estimated_time * 1.1)
            }
        }

    except Exception as e:
        logger.error(f"Error estimating delivery time: {e}")
        # Fallback to simple calculation
        # 10 minutes per km, minimum 30 minutes
        fallback_time = max(30, int(distance_km * 10))
        return {
            "estimated_minutes": fallback_time,
            "estimated_range": {
                "min_minutes": int(fallback_time * 0.9),
                "max_minutes": int(fallback_time * 1.1)
            },
            "fallback": True
        }


def apply_surge_pricing(base_fee: float, traffic_data: Dict[str, Any], weather_data: Dict[str, Any],
                        rider_data: Dict[str, Any], distance_km: float) -> Dict[str, Any]:
    """
    Apply comprehensive surge pricing based on multiple factors.

    Args:
        base_fee: Base delivery fee
        traffic_data: Traffic information
        weather_data: Weather information
        rider_data: Rider availability information
        distance_km: Distance in kilometers

    Returns:
        Dictionary with surge pricing breakdown
    """
    try:
        # Get individual multipliers
        traffic_multiplier = traffic_data.get('multiplier', 1.0)
        weather_multiplier = weather_data.get('multiplier', 1.0)
        rider_multiplier = rider_data.get('multiplier', 1.0)

        # Calculate distance-based surge (for very long distances)
        distance_multiplier = 1.0
        if distance_km > DeliveryConfig.LONG_DISTANCE_THRESHOLD_KM:
            distance_multiplier = 1.0 + \
                ((distance_km - DeliveryConfig.LONG_DISTANCE_THRESHOLD_KM) * 0.05)

        # Calculate combined surge multiplier
        combined_multiplier = traffic_multiplier * \
            weather_multiplier * rider_multiplier * distance_multiplier

        # Cap the maximum surge to prevent excessive fees
        max_surge = DeliveryConfig.MAX_SURGE_MULTIPLIER
        capped_multiplier = min(combined_multiplier, max_surge)

        # Calculate surged fee
        surged_fee = base_fee * capped_multiplier
        surge_amount = surged_fee - base_fee

        return {
            "base_fee": base_fee,
            "surged_fee": surged_fee,
            "surge_amount": surge_amount,
            "total_multiplier": capped_multiplier,
            "was_capped": combined_multiplier > max_surge,
            "breakdown": {
                "traffic_multiplier": traffic_multiplier,
                "weather_multiplier": weather_multiplier,
                "rider_multiplier": rider_multiplier,
                "distance_multiplier": distance_multiplier,
                "combined_multiplier": combined_multiplier
            },
            "factors": {
                "traffic_level": traffic_data.get('level', 'unknown'),
                "weather_condition": weather_data.get('condition', 'unknown'),
                "rider_availability": rider_data.get('level', 'unknown'),
                "is_long_distance": distance_km > 15
            }
        }

    except Exception as e:
        logger.error(f"Error applying surge pricing: {e}")
        return {
            "base_fee": base_fee,
            "surged_fee": base_fee,
            "surge_amount": 0.0,
            "total_multiplier": 1.0,
            "error": str(e)
        }

# -------------------------
# 5. Enhanced Main Calculation Functions
# -------------------------


def apply_promo_code(promo_code: str, user_obj: Any, order_value: float, distance_km: float, 
                     vendor_obj: Any = None, delivery_fee: float = 0.0) -> Dict[str, Any]:
    """
    Standalone helper to apply a promo code and return the discount and metadata.
    """
    from product.promo_models import PromoCode
    from django.utils import timezone
    from django.db.models import Q

    if not delivery_fee:
        raise ValueError("Delivery fee must be provided to apply promo code")
    
    promo_info = {
        "is_applied": False,
        "code": None,
        "message": None,
        "type": None,
        "discount_amount": 0.0,
        "affects_delivery": False
    }

    now_time = timezone.now()
    promo_obj = None

    if promo_code:
        promo_obj = PromoCode.objects.filter(code__iexact=promo_code, is_active=True).first()
        if not promo_obj:
            promo_info["message"] = "Invalid promo code"
            return promo_info
    else:
        from product.models import Order
        # Check for automatic new user promo first
        if user_obj and user_obj.is_authenticated and not Order.objects.filter(user=user_obj).exclude(status='canceled').exists():
            promo_obj = PromoCode.objects.filter(is_new_user_promo=True, is_automatic=True, is_active=True).first()
            
        # Fallback to other automatic promos
        if not promo_obj:
            promo_obj = PromoCode.objects.filter(is_automatic=True, is_active=True, start_date__lte=now_time).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=now_time)
            ).first()

    print(f"Applying promo code: {promo_code}, found promo: {promo_obj}")
    if promo_obj:
        is_valid, validation_msg = promo_obj.is_valid_for_calculation(
            user=user_obj,
            order_value=order_value,
            distance=distance_km,
            vendor=vendor_obj
        )

        if is_valid:
            promo_info["is_applied"] = True
            promo_info["code"] = promo_obj.code
            promo_info["type"] = promo_obj.promo_type
            
            discount_amount = 0.0
            if promo_obj.promo_type == 'free_delivery':
                discount_amount = delivery_fee
                promo_info["affects_delivery"] = True
            elif promo_obj.promo_type == 'discounted_delivery':
                discount_amount = min(delivery_fee, float(promo_obj.value))
                promo_info["affects_delivery"] = True
            elif promo_obj.promo_type == 'fixed_amount':
                discount_amount = float(promo_obj.value)
            elif promo_obj.promo_type == 'percentage':
                discount_amount = (float(promo_obj.value) / 100) * float(order_value)
                print(f"Calculated percentage discount: {discount_amount} from order value: {order_value} and percentage: {promo_obj.value}") 
                if promo_obj.max_discount:
                    discount_amount = min(discount_amount, float(promo_obj.max_discount))

            promo_info["discount_amount"] = discount_amount
            promo_info["message"] = "Promo applied successfully"
        else:
            promo_info["message"] = validation_msg

    return promo_info


def calculate_delivery_fee(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                           order_value: float = 0, item_count: int = 1, weight_kg: float = 1.0,
                           vendor_id: str = None, customer_id: str = None,
                           include_time_estimate: bool = True, promo_code: str = None, **kwargs) -> Dict[str, Any]:
    """
    Enhanced delivery fee calculation with comprehensive features.

    Args:
        origin_lat, origin_lon: Vendor coordinates
        dest_lat, dest_lon: Customer coordinates
        order_value: Total order value (for percentage-based fees)
        item_count: Number of items in the order
        weight_kg: Total weight of the order
        vendor_id: Vendor identifier for vendor-specific pricing
        customer_id: Customer identifier for loyalty discounts
        include_time_estimate: Whether to include delivery time estimation

    Returns:
        Comprehensive dictionary with fee breakdown and additional information
    """
    from account.models import User
    from product.models import PlatformSettings
    # print all the argumaet
    calculation_start = datetime.now()
    calculation_id = f"calc_{int(calculation_start.timestamp())}"

    logger.info(
        f"Starting delivery fee calculation {calculation_id} for route: ({origin_lat}, {origin_lon}) -> ({dest_lat}, {dest_lon})")

    # Input validation
    try:
        # --- DELIVERY PERCENTAGE OFF LOGIC ---
        # This will be applied after all surcharges, before min/max constraints
        delivery_discount_percentage = None
        # 1. User-specific
        user_obj = None
        if customer_id:
            try:
                user_obj = User.objects.filter(id=customer_id).first()
                if user_obj and user_obj.delivery_percentage_off is not None:
                    delivery_discount_percentage = user_obj.delivery_percentage_off
            except Exception:
                pass
        # 2. Category-specific (SystemCategory)
        if delivery_discount_percentage is None and vendor_id:
            try:
                # Try to get vendor's system category via vendor_id
                from account.models import Vendor
                vendor = Vendor.objects.filter(id=vendor_id).first()
                if vendor and vendor.system_category and vendor.system_category.delivery_percentage_off is not None:
                    delivery_discount_percentage = vendor.system_category.delivery_percentage_off
            except Exception:
                pass
        # 3. Platform/global
        if delivery_discount_percentage is None:
            try:
                platform_settings = PlatformSettings.get_settings()
                if platform_settings.delivery_percentage_off is not None:
                    delivery_discount_percentage = platform_settings.delivery_percentage_off
            except Exception:
                pass
        # Validate coordinates
        if not all(isinstance(coord, (int, float)) for coord in [origin_lat, origin_lon, dest_lat, dest_lon]):
            raise ValueError("All coordinates must be numeric")

        if not (-90 <= origin_lat <= 90) or not (-90 <= dest_lat <= 90):
            raise ValueError("Latitude must be between -90 and 90")

        if not (-180 <= origin_lon <= 180) or not (-180 <= dest_lon <= 180):
            raise ValueError("Longitude must be between -180 and 180")

        # Validate other parameters
        if order_value < 0:
            raise ValueError("Order value cannot be negative")

        if item_count < 1:
            raise ValueError("Item count must be at least 1")

        if weight_kg < 0:
            raise ValueError("Weight cannot be negative")

        logger.debug(
            f"Input validation passed for calculation {calculation_id}")

    except ValueError as e:
        logger.error(
            f"Input validation failed for calculation {calculation_id}: {str(e)}")
        return {
            "error": f"Invalid input: {str(e)}",
            "calculation_id": calculation_id,
            "timestamp": calculation_start.isoformat(),
            "success": False
        }

    try:

        # 1. Calculate distance
        logger.debug(
            f"Step 1: Calculating distance for calculation {calculation_id}")
        distance_km = get_distance_between_two_location(
            origin_lat, origin_lon, dest_lat, dest_lon)
        if distance_km is None:
            raise ValueError(
                "Could not calculate distance between coordinates")

        if distance_km > DeliveryConfig.MAX_DISTANCE_KM:
            raise ValueError(
                f"Distance {distance_km:.2f}km exceeds maximum allowed distance of {DeliveryConfig.MAX_DISTANCE_KM}km")

        logger.debug(
            f"Calculated distance: {distance_km:.2f} km for calculation {calculation_id}")

        # 2. Get base fee with time-based pricing
        logger.debug(
            f"Step 2: Calculating base fee for calculation {calculation_id}")
        try:
            base_fee_data = get_base_fee(distance_km)
            base_fee = base_fee_data['time_adjusted_fee']
            logger.debug(
                f"Base fee calculated: ₦{base_fee:.2f} for calculation {calculation_id}")
        except Exception as e:
            logger.warning(
                f"Base fee calculation failed for calculation {calculation_id}: {e}")
            # Fallback to simple distance-based calculation
            base_fee = max(DeliveryConfig.MIN_DELIVERY_FEE, distance_km * 150)
            base_fee_data = {"time_adjusted_fee": base_fee, "fallback": True}

        # 3. Get real-time dynamic factors
        logger.debug(
            f"Step 3: Fetching real-time factors for calculation {calculation_id}")
        try:
            traffic_data = fetch_traffic_level(
                (origin_lat, origin_lon), (dest_lat, dest_lon))
            logger.debug(
                f"Traffic data: {traffic_data.get('level', 'unknown')} (multiplier: {traffic_data.get('multiplier', 1.0)}) for calculation {calculation_id}")
        except Exception as e:
            logger.warning(
                f"Traffic data fetch failed for calculation {calculation_id}: {e}")
            traffic_data = {"level": "moderate",
                            "multiplier": 1.3, "source": "fallback"}

        try:
            weather_data = fetch_weather_factor(dest_lat, dest_lon)
            logger.debug(
                f"Weather data: {weather_data.get('condition', 'unknown')} (multiplier: {weather_data.get('multiplier', 1.0)}) for calculation {calculation_id}")
        except Exception as e:
            logger.warning(
                f"Weather data fetch failed for calculation {calculation_id}: {e}")
            weather_data = {"condition": "clear",
                            "multiplier": 1.0, "source": "fallback"}

        try:
            rider_data = fetch_rider_availability()
            logger.debug(
                f"Rider availability: {rider_data.get('level', 'unknown')} (multiplier: {rider_data.get('multiplier', 1.0)}) for calculation {calculation_id}")
        except Exception as e:
            logger.warning(
                f"Rider availability fetch failed for calculation {calculation_id}: {e}")
            rider_data = {"level": "normal",
                          "multiplier": 1.0, "source": "fallback"}

        # 4. Apply surge pricing
        logger.debug(
            f"Step 4: Applying surge pricing for calculation {calculation_id}")
        try:
            surge_data = apply_surge_pricing(
                base_fee, traffic_data, weather_data, rider_data, distance_km)
            logger.debug(
                f"Surge pricing applied: {surge_data.get('multiplier', 1.0)}x (₦{surge_data.get('surge_amount', 0):.2f} increase) for calculation {calculation_id}")
        except Exception as e:
            logger.warning(
                f"Surge pricing calculation failed for calculation {calculation_id}: {e}")
            surge_data = {"surged_fee": base_fee, "surge_amount": 0,
                          "multiplier": 1.0, "fallback": True}

        # 5. Calculate vendor-specific adjustments
        logger.debug(
            f"Step 5: Calculating vendor-specific adjustments for calculation {calculation_id}")
        vendor_fee_data = {"adjustment": 0.0, "multiplier": 1.0}
        if vendor_id:
            try:
                vendor_fee_data = calculate_vendor_specific_fee(
                    vendor_id, surge_data['surged_fee'])
                current_fee = vendor_fee_data['adjusted_fee']
                logger.debug(
                    f"Vendor adjustment applied: {vendor_fee_data.get('multiplier', 1.0)}x (₦{vendor_fee_data.get('adjustment', 0):.2f}) for calculation {calculation_id}")
            except Exception as e:
                logger.warning(
                    f"Vendor fee calculation failed for calculation {calculation_id}: {e}")
                current_fee = surge_data['surged_fee']
                vendor_fee_data = {"adjustment": 0.0, "multiplier": 1.0,
                                   "adjusted_fee": current_fee, "fallback": True}
        else:
            current_fee = surge_data['surged_fee']
            logger.debug(
                f"No vendor ID provided for calculation {calculation_id}")

        # 6. Calculate item and weight surcharges
        logger.debug(
            f"Step 6: Calculating surcharges for calculation {calculation_id}")
        try:
            item_surcharge = 0.0
            if item_count > DeliveryConfig.FREE_ITEM_THRESHOLD:
                excess_items = item_count - DeliveryConfig.FREE_ITEM_THRESHOLD
                item_surcharge = excess_items * DeliveryConfig.ITEM_SURCHARGE_PER_ITEM
                logger.debug(
                    f"Item surcharge: ₦{item_surcharge:.2f} for {excess_items} excess items for calculation {calculation_id}")

            # Find weight tier
            weight_surcharge = 0.0
            if weight_kg > DeliveryConfig.FREE_WEIGHT_THRESHOLD_KG:
                excess_weight = weight_kg - DeliveryConfig.FREE_WEIGHT_THRESHOLD_KG
                weight_surcharge = excess_weight * DeliveryConfig.WEIGHT_SURCHARGE_PER_KG
                logger.debug(
                    f"Weight surcharge: ₦{weight_surcharge:.2f} for {excess_weight:.2f}kg excess weight for calculation {calculation_id}")

        except Exception as e:
            logger.warning(
                f"Surcharge calculation failed for calculation {calculation_id}: {e}")
            item_surcharge = 0.0
            weight_surcharge = 0.0

        # 7. Add surcharges
        fee_with_surcharges = current_fee + item_surcharge + weight_surcharge
        logger.debug(
            f"Fee with surcharges: ₦{fee_with_surcharges:.2f} for calculation {calculation_id}")

        # 7.1 Calculate service fee (Chowdeck style: percentage of order value, capped)
        service_fee = 0.0
        if order_value > 0:
            raw_service_fee = (
                DeliveryConfig.SERVICE_FEE_PERCENTAGE / 100) * order_value
            service_fee = min(raw_service_fee, DeliveryConfig.MAX_SERVICE_FEE)
            logger.debug(
                f"Service fee: ₦{service_fee:.2f} (based on {DeliveryConfig.SERVICE_FEE_PERCENTAGE}% of ₦{order_value:.2f}, capped at ₦{DeliveryConfig.MAX_SERVICE_FEE:.2f}) for calculation {calculation_id}")

        # 8. Apply loyalty discount
        logger.debug(
            f"Step 8: Applying loyalty discount for calculation {calculation_id}")
        loyalty_data = {"discount_amount": 0.0, "loyalty_level": "none"}
        if customer_id:
            try:
                loyalty_data = calculate_loyalty_discount(
                    customer_id, fee_with_surcharges)
                final_fee = loyalty_data['discounted_fee']
                logger.debug(
                    f"Loyalty discount applied: ₦{loyalty_data.get('discount_amount', 0):.2f} ({loyalty_data.get('loyalty_level', 'unknown')} tier) for calculation {calculation_id}")
            except Exception as e:
                logger.warning(
                    f"Loyalty discount calculation failed for calculation {calculation_id}: {e}")
                final_fee = fee_with_surcharges
                loyalty_data = {"discount_amount": 0.0, "loyalty_level": "none",
                                "discounted_fee": final_fee, "fallback": True}
        else:
            final_fee = fee_with_surcharges
            logger.debug(
                f"No customer ID provided for calculation {calculation_id}")

        # Apply delivery percentage off (after surcharges, before min/max)
        if delivery_discount_percentage is not None and delivery_discount_percentage > 0:
            discount_amount = (delivery_discount_percentage / 100) * final_fee
            logger.debug(
                f"Applying delivery percentage off: {delivery_discount_percentage}% (₦{discount_amount:.2f}) for calculation {calculation_id}")
            final_fee -= discount_amount
        # Apply min/max constraints
        original_final_fee = final_fee
        final_fee = max(DeliveryConfig.MIN_DELIVERY_FEE, min(
            final_fee, DeliveryConfig.MAX_DELIVERY_FEE))
        if final_fee != original_final_fee:
            logger.debug(
                f"Fee constrained from ₦{original_final_fee:.2f} to ₦{final_fee:.2f} for calculation {calculation_id}")

        # --- NEW PROMO CODE SYSTEM INTEGRATION ---
        from account.models import Vendor
        vendor_obj = Vendor.objects.filter(id=vendor_id).first() if vendor_id else None
        
        original_final_fee = final_fee # Save before promo
        
        promo_info = apply_promo_code(
            promo_code=promo_code,
            user_obj=user_obj,
            order_value=order_value,
            distance_km=distance_km,
            vendor_obj=vendor_obj,
            current_fee=final_fee
        )

        if promo_info["is_applied"] and promo_info["affects_delivery"]:
            final_fee -= promo_info["discount_amount"]
            final_fee = max(0, final_fee)

        # 8.1 Final total including service fee
        grand_total = final_fee + service_fee
        if promo_info["is_applied"] and not promo_info["affects_delivery"]:
            grand_total -= float(promo_info["discount_amount"])
        
        grand_total = max(0, grand_total)
        logger.debug(
            f"Grand total with service fee: ₦{grand_total:.2f} for calculation {calculation_id}")

        # 9. Estimate delivery time
        logger.debug(
            f"Step 9: Estimating delivery time for calculation {calculation_id}")
        time_estimate = {}
        if include_time_estimate:
            try:
                time_estimate = estimate_delivery_time(
                    distance_km, traffic_data, weather_data)
                logger.debug(
                    f"Delivery time estimated: {time_estimate.get('estimated_minutes', 'unknown')} minutes for calculation {calculation_id}")
            except Exception as e:
                logger.warning(
                    f"Delivery time estimation failed for calculation {calculation_id}: {e}")
                time_estimate = {"error": str(e), "fallback": True}

        # 10. Calculate processing time
        calculation_end = datetime.now()
        calculation_time = (
            calculation_end - calculation_start).total_seconds()
        logger.debug(
            f"Calculation {calculation_id} completed in {calculation_time:.3f} seconds")

        # 11. Prepare comprehensive response
        result = {
            "total_fee": round(grand_total, 2),
            "delivery_fee": round(final_fee, 2),
            "original_fee": round(original_final_fee, 2),
            "service_fee": round(service_fee, 2),
            "currency": "NGN",
            "calculation_id": calculation_id,
            "calculation_timestamp": calculation_end.isoformat(),
            "calculation_time_ms": round(calculation_time * 1000, 2),
            "success": True,
            # Detailed breakdown
            "breakdown": {
                "base_fee": base_fee,
                "surge_amount": surge_data['surge_amount'],
                "vendor_adjustment": vendor_fee_data.get('adjustment', 0.0),
                "item_surcharge": item_surcharge,
                "weight_surcharge": weight_surcharge,
                "loyalty_discount": -loyalty_data.get('discount_amount', 0.0),
                "subtotal_before_discount": fee_with_surcharges,
                "delivery_percentage_off": float(delivery_discount_percentage) if delivery_discount_percentage is not None else 0.0,
                "delivery_discount_amount": round(discount_amount, 2) if delivery_discount_percentage is not None and delivery_discount_percentage > 0 else 0.0,
                "promo_discount_amount": float(promo_info["discount_amount"]),
                "service_fee": round(service_fee, 2),
                "final_delivery_fee": final_fee,
                "grand_total": grand_total
            },
            "promo_details": promo_info,
            # Route information
            "route": {
                "distance_km": distance_km,
                "origin": {"lat": origin_lat, "lon": origin_lon},
                "destination": {"lat": dest_lat, "lon": dest_lon}
            },
            # Real-time factors
            "factors": {
                "traffic": {
                    "level": traffic_data.get('level', 'unknown'),
                    "multiplier": traffic_data.get('multiplier', 1.0),
                    "source": traffic_data.get('source', 'unknown')
                },
                "weather": {
                    "condition": weather_data.get('condition', 'unknown'),
                    "multiplier": weather_data.get('multiplier', 1.0),
                    "source": weather_data.get('source', 'unknown')
                },
                "rider_availability": {
                    "level": rider_data.get('level', 'unknown'),
                    "multiplier": rider_data.get('multiplier', 1.0),
                    "source": rider_data.get('source', 'unknown')
                }
            },
            # Additional details
            "surge_details": surge_data,
            "vendor_details": vendor_fee_data,
            "loyalty_details": loyalty_data,
            "base_fee_details": base_fee_data,
            # Order details
            "order_info": {
                "item_count": item_count,
                "weight_kg": weight_kg,
                "order_value": order_value
            }
        }

        # Add time estimate if requested
        if include_time_estimate and time_estimate:
            result["delivery_estimate"] = time_estimate

        logger.info(
            f"Delivery fee calculation {calculation_id} completed successfully: ₦{final_fee:.2f} for {distance_km:.2f}km route (processing time: {calculation_time:.3f}s)")
        return result

    except Exception as e:
        logger.error(
            f"Error in enhanced delivery fee calculation {calculation_id}: {e}", exc_info=True)

        # Comprehensive fallback calculation
        try:
            logger.info(
                f"Attempting fallback calculation for {calculation_id}")
            fallback_distance = get_distance_between_two_location(
                origin_lat, origin_lon, dest_lat, dest_lon)
            if fallback_distance is None:
                fallback_distance = 5.0  # Default fallback distance
                logger.warning(
                    f"Using default fallback distance for calculation {calculation_id}")

            fallback_fee = max(DeliveryConfig.MIN_DELIVERY_FEE,
                               fallback_distance * 200)  # 200 NGN per km
            logger.info(
                f"Fallback calculation {calculation_id} completed: ₦{fallback_fee:.2f}")

            return {
                "total_fee": round(fallback_fee, 2),
                "currency": "NGN",
                "calculation_id": calculation_id,
                "calculation_timestamp": datetime.now().isoformat(),
                "success": False,
                "breakdown": {
                    "base_fee": fallback_fee,
                    "distance_km": fallback_distance
                },
                "route": {
                    "distance_km": fallback_distance,
                    "origin": {"lat": origin_lat, "lon": origin_lon},
                    "destination": {"lat": dest_lat, "lon": dest_lon}
                },
                "error": str(e),
                "fallback": True,
                "fallback_method": "distance_based"
            }
        except Exception as fallback_error:
            logger.error(
                f"Fallback calculation {calculation_id} also failed: {fallback_error}")
            return {
                "total_fee": DeliveryConfig.MIN_DELIVERY_FEE,
                "currency": "NGN",
                "calculation_id": calculation_id,
                "calculation_timestamp": datetime.now().isoformat(),
                "success": False,
                "error": f"Primary: {str(e)}, Fallback: {str(fallback_error)}",
                "fallback": True,
                "fallback_method": "minimum_fee"
            }


def get_delivery_fee_estimate(distance_km: float, vendor_type: str = 'restaurant',
                              customer_loyalty: str = 'bronze', current_conditions: bool = True) -> Dict[str, Any]:
    """
    Quick delivery fee estimate without full calculation.
    Useful for displaying approximate fees before exact coordinates are available.

    Args:
        distance_km: Estimated distance in kilometers
        vendor_type: Type of vendor (restaurant, grocery, electronics, etc.)
        customer_loyalty: Customer loyalty level (bronze, silver, gold, platinum)
        current_conditions: Whether to factor in current traffic/weather conditions

    Returns:
        Dictionary with fee estimate and range
    """
    try:
        # Get base fee
        base_fee_data = get_base_fee(distance_km)
        base_fee = base_fee_data['time_adjusted_fee']

        # Apply vendor multiplier
        vendor_multiplier = DeliveryConfig.VENDOR_TYPE_MULTIPLIERS.get(
            vendor_type, 1.0)
        vendor_adjusted_fee = base_fee * vendor_multiplier

        # Apply loyalty discount
        loyalty_discount = DeliveryConfig.LOYALTY_DISCOUNTS.get(
            customer_loyalty, 0.0)
        discounted_fee = vendor_adjusted_fee * (1 - loyalty_discount)

        # Estimate surge range based on current conditions
        if current_conditions:
            # Simulate current conditions for estimate
            min_surge = 1.0  # Best case
            max_surge = 2.0  # Reasonable worst case
        else:
            min_surge = max_surge = 1.0

        min_fee = discounted_fee * min_surge
        max_fee = discounted_fee * max_surge

        return {
            "estimated_fee": round(discounted_fee, 2),
            "fee_range": {
                "min": round(min_fee, 2),
                "max": round(max_fee, 2)
            },
            "base_fee": base_fee,
            "vendor_type": vendor_type,
            "customer_loyalty": customer_loyalty,
            "distance_km": distance_km,
            "includes_current_conditions": current_conditions,
            "disclaimer": "Actual fee may vary based on real-time conditions"
        }

    except Exception as e:
        logger.error(f"Error in delivery fee estimate: {e}")
        fallback_fee = max(DeliveryConfig.MIN_DELIVERY_FEE, distance_km * 200)
        return {
            "estimated_fee": round(fallback_fee, 2),
            "fee_range": {
                "min": round(fallback_fee * 0.8, 2),
                "max": round(fallback_fee * 1.5, 2)
            },
            "distance_km": distance_km,
            "error": str(e),
            "fallback": True
        }


def calculate_fee_from_coords(origin_coords: Tuple[float, float], dest_coords: Tuple[float, float],
                              **kwargs) -> Dict[str, Any]:
    """
    Enhanced wrapper function for coordinate-based fee calculation.

    Args:
        origin_coords: (lat, lon) tuple for vendor
        dest_coords: (lat, lon) tuple for customer
        **kwargs: Additional parameters (order_value, item_count, weight_kg, vendor_id, customer_id, etc.)

    Returns:
        Dictionary with comprehensive fee calculation results
    """
    return calculate_delivery_fee(
        origin_coords[0], origin_coords[1],
        dest_coords[0], dest_coords[1],
        **kwargs
    )


def calculate_rider_fare(distance_km: float) -> float:
    """
    Calculate the fare that is paid to the rider.
    Logic: Base fare for first X km, then incremental charge for every Y km.
    """
    from decimal import Decimal
    import math

    base_fare = Decimal(str(DeliveryConfig.BASE_FARE))
    inc_charge = Decimal(str(DeliveryConfig.INCREMENTAL_CHARGE))
    base_dist = Decimal(str(DeliveryConfig.BASE_DISTANCE_RANGE))
    inc_dist = Decimal(str(DeliveryConfig.INCREMENTAL_DISTANCE))

    dist = Decimal(str(distance_km))

    if dist <= base_dist:
        return float(base_fare)

    extra_dist = dist - base_dist
    multiples = math.ceil(extra_dist / inc_dist)
    total_fare = base_fare + (Decimal(multiples) * inc_charge)

    return float(total_fare)


def check_address_in_zone(lat: float, lon: float) -> Optional[Any]:
    """
    Check if a coordinate falls within a predefined delivery zone using Point-in-Polygon.
    """
    from product.models import DeliveryZone

    def is_point_in_polygon(x, y, poly):
        n = len(poly)
        inside = False
        if n < 3:
            return False

        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    try:
        zones = DeliveryZone.objects.filter(is_active=True)
        for zone in zones:
            boundary = zone.boundary
            if boundary and is_point_in_polygon(float(lat), float(lon), boundary):
                return zone
    except Exception as e:
        print(f"Error checking address in zone: {e}")
    return None


def calculate_delivery_price_v2(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                                order_value: float = 0, item_count: int = 1, weight_kg: float = 1.0,
                                vendor_id: str = None, customer_id: str = None,
                                order_type: str = 'same_day') -> Dict[str, Any]:
    """
    Revised delivery fee calculation based on the Riders App Model.
    """
    from decimal import Decimal

    # 1. Distance Calculation
    distance_km = get_distance_between_two_location(
        origin_lat, origin_lon, dest_lat, dest_lon)
    if distance_km is None:
        distance_km = 0.5  # Fallback

    # 2. Check for Maximum Distance
    max_dist = float(DeliveryConfig.MAX_DISTANCE_KM)
    if distance_km > max_dist:
        return {
            "success": False,
            "error": f"Distance {distance_km:.2f}km exceeds maximum allowed ({max_dist}km)",
            "total_fee": 0
        }

    # 3. Determine if Zone-Based (Marketplace)
    # If order_type is marketplace or we find a zone
    zone = check_address_in_zone(dest_lat, dest_lon)
    estate_fee = 0.0
    if zone:
        rider_fee = float(zone.fixed_fee)
        is_zone_based = True

        # Add Estate Gate Pass Fee if applicable
        from product.models import EstateGatePass
        gate_pass = EstateGatePass.objects.filter(location_zone=zone).first()
        if gate_pass:
            estate_fee = float(gate_pass.gate_fee_bike)
    else:
        rider_fee = calculate_rider_fare(distance_km)
        is_zone_based = False

    # 4. Platform Operational Fee
    op_fee = float(DeliveryConfig.PLATFORM_OPERATIONAL_FEE)
    customer_fee = rider_fee + op_fee + estate_fee

    # 5. Service Fee (Existing logic)
    service_fee = 0.0
    if order_value > 0:
        raw_service_fee = (
            float(DeliveryConfig.SERVICE_FEE_PERCENTAGE) / 100) * float(order_value)
        service_fee = min(raw_service_fee, float(
            DeliveryConfig.MAX_SERVICE_FEE))

    return {
        "success": True,
        "total_fee": round(customer_fee + service_fee, 2),
        "delivery_fee": round(customer_fee, 2),
        "rider_earning": round(rider_fee, 2),
        "platform_fee": round(op_fee, 2),
        "service_fee": round(service_fee, 2),
        "distance_km": round(distance_km, 2),
        "is_zone_based": is_zone_based,
        "breakdown": {
            "rider_fare": round(rider_fee, 2),
            "platform_operational_fee": round(op_fee, 2),
            "estate_gate_pass_fee": round(estate_fee, 2),
            "service_fee": round(service_fee, 2)
        }
    }
