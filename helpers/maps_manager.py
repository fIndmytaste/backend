import time
import uuid
from django.core.cache import cache
from django.conf import settings


class GoogleMapsManager:
    """
    Manages Google Maps API usage to optimize costs and performance.
    - Handles Session Tokens for Places API (Autocomplete -> Details)
    - Caches distance/time estimates
    - Implements simple rate limiting per user/rider
    """

    # Session tokens are valid for up to several minutes and should be reused
    # for a single autocomplete-to-details flow.
    SESSION_TOKEN_TIMEOUT = 180  # 3 minutes

    @staticmethod
    def get_or_create_session_token(user_id):
        cache_key = f"google_maps_session_token_{user_id}"
        token = cache.get(cache_key)
        if not token:
            token = str(uuid.uuid4())
            cache.set(cache_key, token,
                      timeout=GoogleMapsManager.SESSION_TOKEN_TIMEOUT)
        return token

    @staticmethod
    def clear_session_token(user_id):
        cache_key = f"google_maps_session_token_{user_id}"
        cache.delete(cache_key)

    @staticmethod
    def get_cached_distance(origin, destination):
        """
        Get distance from cache if recently calculated.
        origin/destination: (lat, lng) tuples
        """
        cache_key = f"dist_{origin}_{destination}"
        return cache.get(cache_key)

    @staticmethod
    def cache_distance(origin, destination, distance_data, timeout=3600):
        cache_key = f"dist_{origin}_{destination}"
        cache.set(cache_key, distance_data, timeout=timeout)

    @staticmethod
    def is_rate_limited(user_id, action="autocomplete", limit=10, period=60):
        """
        Simple rate limiting: max 'limit' calls per 'period' seconds.
        """
        cache_key = f"rate_limit_{action}_{user_id}"
        count = cache.get(cache_key, 0)
        if count >= limit:
            return True
        cache.set(cache_key, count + 1, timeout=period)
        return False
