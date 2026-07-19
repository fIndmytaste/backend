"""
Marketplace availability gating.

The marketplace (Lagos open-market shopping) only operates inside Lagos State,
so users whose location or address resolves outside Lagos must not be offered
marketplace content.
"""

from helpers.vendor_discovery import resolve_request_coordinates

# Lagos State bounding box (Badagry to Epe, Atlantic coast to the Ogun border).
# Deliberately generous: a border-town false positive is harmless because the
# marketplace vendors themselves are all inside Lagos.
LAGOS_MIN_LATITUDE = 6.35
LAGOS_MAX_LATITUDE = 6.75
LAGOS_MIN_LONGITUDE = 2.70
LAGOS_MAX_LONGITUDE = 4.35

MARKETPLACE_UNAVAILABLE_MESSAGE = 'Marketplace is only available in Lagos.'


def coordinates_within_lagos(latitude, longitude):
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return False
    return (
        LAGOS_MIN_LATITUDE <= latitude <= LAGOS_MAX_LATITUDE
        and LAGOS_MIN_LONGITUDE <= longitude <= LAGOS_MAX_LONGITUDE
    )


def marketplace_available_for_request(request):
    """
    True unless the request resolves to coordinates outside Lagos.

    Coordinates come from ?latitude/?longitude query params, falling back to
    the authenticated user's active address. An unknown location fails open so
    marketplace is never hidden from a Lagos user who has not shared a
    location yet.
    """
    latitude, longitude = resolve_request_coordinates(request)
    if latitude is None or longitude is None:
        return True
    return coordinates_within_lagos(latitude, longitude)
