"""
Admin endpoints powering the Next.js "Delivery Settings" page.

Two resources are exposed so a non-technical operator can tune delivery pricing
without touching Django admin or raw JSON:

  1. Platform Settings  -> rider pay, commission and global discount
     (product.PlatformSettings singleton, consumed by calculate_rider_fare).
  2. Delivery Config    -> the customer-facing surge engine parameters
     (helpers.DeliveryConfiguration key/value rows, consumed by
      calculate_delivery_fee). Values are returned/accepted as already-typed
      JSON (never raw strings); rows are created on demand with the correct
      metadata so DeliveryConfiguration.full_clean() passes.
"""
import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from helpers.models import ConfigurationManager, DeliveryConfiguration
from helpers.order_utils import DeliveryConfig
from helpers.response.response_format import bad_request_response, success_response
from product.models import PlatformSettings


# ─────────────────────────────────────────────────────────────────────────────
# 1. Platform Settings (rider pay + commission + discounts)
# ─────────────────────────────────────────────────────────────────────────────

# field -> coercion kind. Kept explicit so a stray key in the payload is ignored.
_PLATFORM_DECIMAL_FIELDS = [
    'base_fare',
    'incremental_charge',
    'base_distance_range',
    'incremental_distance',
    'platform_operational_fee',
    'max_delivery_distance',
    'default_commission_percentage',
    'rider_commission_percentage',
]
_PLATFORM_NULLABLE_DECIMAL_FIELDS = [
    'delivery_percentage_off',
]
_PLATFORM_BOOL_FIELDS = [
    'is_commission_active',
    'is_multi_stop_enabled',
]


def _platform_settings_to_dict(settings):
    def dec(value):
        return str(value) if value is not None else None

    return {
        # rider pay
        'base_fare': dec(settings.base_fare),
        'incremental_charge': dec(settings.incremental_charge),
        'base_distance_range': dec(settings.base_distance_range),
        'incremental_distance': dec(settings.incremental_distance),
        'platform_operational_fee': dec(settings.platform_operational_fee),
        'max_delivery_distance': dec(settings.max_delivery_distance),
        'is_multi_stop_enabled': settings.is_multi_stop_enabled,
        # commission + discounts
        'default_commission_percentage': dec(settings.default_commission_percentage),
        'rider_commission_percentage': dec(settings.rider_commission_percentage),
        'delivery_percentage_off': dec(settings.delivery_percentage_off),
        'is_commission_active': settings.is_commission_active,
        'updated_at': settings.updated_at.isoformat() if settings.updated_at else None,
    }


class AdminPlatformSettingsView(APIView):
    """
    GET   /admin-manager/pricing/platform-settings/
    PATCH /admin-manager/pricing/platform-settings/
        Update rider pay / commission / discount fields on the singleton.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = PlatformSettings.get_settings()
        return success_response(
            message="Platform settings retrieved.",
            data=_platform_settings_to_dict(settings),
        )

    def patch(self, request):
        settings = PlatformSettings.get_settings()
        data = request.data

        try:
            for field in _PLATFORM_DECIMAL_FIELDS:
                if field in data and data[field] is not None:
                    value = Decimal(str(data[field]))
                    if value < 0:
                        return bad_request_response(
                            message=f"{field.replace('_', ' ').capitalize()} cannot be negative."
                        )
                    setattr(settings, field, value)

            for field in _PLATFORM_NULLABLE_DECIMAL_FIELDS:
                if field in data:
                    raw = data[field]
                    setattr(
                        settings,
                        field,
                        Decimal(str(raw)) if raw not in (None, "") else None,
                    )

            for field in _PLATFORM_BOOL_FIELDS:
                if field in data:
                    setattr(settings, field, bool(data[field]))
        except (InvalidOperation, TypeError, ValueError):
            return bad_request_response(message="One or more values are not valid numbers.")

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            settings.updated_by = user

        settings.save()
        return success_response(
            message="Platform settings updated.",
            data=_platform_settings_to_dict(settings),
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Delivery Config (surge engine)
# ─────────────────────────────────────────────────────────────────────────────

# Metadata for every key the page can create/update. Mirrors
# helpers/management/commands/populate_delivery_config.py so that rows created on
# demand satisfy DeliveryConfiguration.full_clean() (data_type, default_value,
# key-specific validators and min/max ranges). service_fee_percentage /
# max_service_fee are not in the seed command, so they are defined here.
CONFIG_META = {
    'base_pricing_tiers': {
        'category': 'pricing', 'data_type': 'json',
        'description': 'Distance tiers: base fee + per-0.5 km rate within each range',
        'default': [
            {"max_distance": 1.2, "base_fee": 800, "per_half_km_rate": 100},
            {"max_distance": 5, "base_fee": 1200, "per_half_km_rate": 80},
            {"max_distance": "inf", "base_fee": 1800, "per_half_km_rate": 100},
        ],
    },
    'peak_hours': {
        'category': 'timing', 'data_type': 'json',
        'description': 'Peak hours with surge multipliers',
        'default': [
            {"start": "07:00", "end": "09:30", "multiplier": 1.3, "name": "Morning Rush"},
            {"start": "12:00", "end": "14:00", "multiplier": 1.2, "name": "Lunch Rush"},
            {"start": "17:00", "end": "20:00", "multiplier": 1.4, "name": "Evening Rush"},
            {"start": "22:00", "end": "23:59", "multiplier": 1.2, "name": "Late Night"},
        ],
    },
    'traffic_multipliers': {
        'category': 'multipliers', 'data_type': 'json',
        'description': 'Traffic condition multipliers',
        'default': {"free_flow": 1.0, "light": 1.1, "moderate": 1.3, "heavy": 1.6, "severe": 2.0},
    },
    'weather_multipliers': {
        'category': 'multipliers', 'data_type': 'json',
        'description': 'Weather condition multipliers',
        'default': {"clear": 1.0, "cloudy": 1.0, "light_rain": 1.2, "heavy_rain": 1.5,
                    "thunderstorm": 1.8, "fog": 1.3, "snow": 2.0},
    },
    'rider_availability_multipliers': {
        'category': 'multipliers', 'data_type': 'json',
        'description': 'Rider availability multipliers',
        'default': {"high": 0.9, "normal": 1.0, "low": 1.3, "critical": 1.8},
    },
    'vendor_type_multipliers': {
        'category': 'multipliers', 'data_type': 'json',
        'description': 'Vendor type multipliers',
        'default': {"restaurant": 1.0, "grocery": 1.1, "pharmacy": 1.2,
                    "electronics": 1.3, "fragile_items": 1.5},
    },
    'loyalty_discounts': {
        'category': 'multipliers', 'data_type': 'json',
        'description': 'Loyalty tier discounts',
        'default': {"bronze": 0.05, "silver": 0.10, "gold": 0.15, "platinum": 0.20},
    },
    'max_distance_km': {
        'category': 'thresholds', 'data_type': 'int',
        'description': 'Maximum delivery distance in kilometers',
        'default': 50, 'min_value': 1, 'max_value': 200,
    },
    'min_delivery_fee': {
        'category': 'pricing', 'data_type': 'int',
        'description': 'Minimum delivery fee in NGN',
        'default': 500, 'min_value': 100, 'max_value': 2000,
    },
    'max_delivery_fee': {
        'category': 'pricing', 'data_type': 'int',
        'description': 'Maximum delivery fee in NGN',
        'default': 10000, 'min_value': 1000, 'max_value': 50000,
    },
    'max_surge_multiplier': {
        'category': 'multipliers', 'data_type': 'float',
        'description': 'Maximum surge pricing multiplier',
        'default': 3.0, 'min_value': 1.0, 'max_value': 5.0,
    },
    'free_item_threshold': {
        'category': 'thresholds', 'data_type': 'int',
        'description': 'Number of free items before surcharge',
        'default': 1, 'min_value': 1, 'max_value': 10,
    },
    'item_surcharge_per_item': {
        'category': 'pricing', 'data_type': 'float',
        'description': 'Surcharge per additional item in NGN',
        'default': 50.0, 'min_value': 0, 'max_value': 500,
    },
    'free_weight_threshold_kg': {
        'category': 'thresholds', 'data_type': 'float',
        'description': 'Free weight limit in kg',
        'default': 2.0, 'min_value': 0.5, 'max_value': 20.0,
    },
    'weight_surcharge_per_kg': {
        'category': 'pricing', 'data_type': 'float',
        'description': 'Surcharge per additional kg in NGN',
        'default': 100.0, 'min_value': 0, 'max_value': 1000,
    },
    'service_fee_percentage': {
        'category': 'pricing', 'data_type': 'float',
        'description': 'Service fee as a percentage of order value',
        'default': 2.5, 'min_value': 0, 'max_value': 100,
    },
    'max_service_fee': {
        'category': 'pricing', 'data_type': 'float',
        'description': 'Maximum service fee in NGN',
        'default': 500.0, 'min_value': 0, 'max_value': 100000,
    },
}

# Order preserved for a stable, readable GET response.
CONFIG_KEYS = list(CONFIG_META.keys())


def _tiers_out(tiers):
    """Fallback/DB tiers -> wire format (open-ended max_distance as null)."""
    out = []
    for tier in tiers or []:
        if not isinstance(tier, dict):
            continue
        md = tier.get('max_distance')
        if md in ('inf', None) or (isinstance(md, float) and md == float('inf')):
            md = None
        out.append({
            'max_distance': md,
            'base_fee': tier.get('base_fee'),
            'per_half_km_rate': tier.get(
                'per_half_km_rate', tier.get('per_km_rate')),
        })
    return out


def _tiers_in(tiers):
    """Wire tiers -> storage format (null/last max_distance stored as 'inf')."""
    if not isinstance(tiers, list) or not tiers:
        raise ValueError("At least one distance tier is required.")
    cleaned = []
    for tier in tiers:
        if not isinstance(tier, dict):
            raise ValueError("Each distance tier must be an object.")
        md = tier.get('max_distance')
        md = 'inf' if md in (None, '', 'inf') else float(md)
        cleaned.append({
            'max_distance': md,
            'base_fee': float(tier.get('base_fee')),
            'per_half_km_rate': float(tier.get('per_half_km_rate')),
        })
    return cleaned


def _serialize(value, data_type):
    if data_type == 'json':
        return json.dumps(value)
    if data_type == 'bool':
        return str(bool(value)).lower()
    return str(value)


def _current_config():
    """Merge hardcoded fallback with any active DB rows (DB wins)."""
    merged = dict(DeliveryConfig._FALLBACK_CONFIG)
    merged.update(ConfigurationManager.get_all_configs())
    return merged


class AdminDeliveryConfigView(APIView):
    """
    GET   /admin-manager/pricing/delivery-config/
        Returns every editable surge-engine parameter as typed JSON.
    PATCH /admin-manager/pricing/delivery-config/
        Create-or-update only the keys present in the payload.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        config = _current_config()
        data = {}
        for key in CONFIG_KEYS:
            value = config.get(key, CONFIG_META[key]['default'])
            data[key] = _tiers_out(value) if key == 'base_pricing_tiers' else value
        return success_response(message="Delivery configuration retrieved.", data=data)

    def patch(self, request):
        data = request.data or {}
        user_email = ''
        if getattr(request, 'user', None) is not None and request.user.is_authenticated:
            user_email = request.user.email or getattr(request.user, 'username', '') or ''

        # Normalise incoming values before any write so a bad payload fails
        # atomically (nothing persisted) with a readable message.
        pending = {}
        try:
            for key, raw in data.items():
                if key not in CONFIG_META:
                    continue  # silently ignore unknown keys
                if key == 'base_pricing_tiers':
                    pending[key] = _tiers_in(raw)
                elif CONFIG_META[key]['data_type'] == 'json':
                    pending[key] = raw
                elif CONFIG_META[key]['data_type'] == 'int':
                    pending[key] = int(raw)
                else:  # float
                    pending[key] = float(raw)
        except (TypeError, ValueError):
            return bad_request_response(message=f"'{key}' has an invalid value.")

        if not pending:
            return bad_request_response(message="No editable settings provided.")

        try:
            for key, value in pending.items():
                self._upsert(key, value, user_email)
        except ValidationError as exc:
            message = "; ".join(exc.messages) if hasattr(exc, 'messages') else str(exc)
            return bad_request_response(message=message)

        # Return the full, freshly-merged config so the UI stays in sync.
        return self.get(request)

    @staticmethod
    def _upsert(key, value, user_email):
        meta = CONFIG_META[key]
        obj, _created = DeliveryConfiguration.objects.get_or_create(
            key=key,
            defaults={
                'category': meta['category'],
                'data_type': meta['data_type'],
                'value': _serialize(value, meta['data_type']),
                'default_value': _serialize(meta['default'], meta['data_type']),
                'description': meta['description'],
                'min_value': meta.get('min_value'),
                'max_value': meta.get('max_value'),
            },
        )
        # Ensure metadata is present on pre-existing rows too, then set the value.
        obj.data_type = meta['data_type']
        if not obj.default_value:
            obj.default_value = _serialize(meta['default'], meta['data_type'])
        if obj.min_value is None and meta.get('min_value') is not None:
            obj.min_value = meta['min_value']
        if obj.max_value is None and meta.get('max_value') is not None:
            obj.max_value = meta['max_value']
        obj.value = _serialize(value, meta['data_type'])
        obj.is_active = True
        obj.updated_by = user_email
        obj.save()  # runs full_clean() and clears the config cache
