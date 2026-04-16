"""
Validation functions for delivery configuration parameters.
"""
import json
from datetime import time
from typing import Any, Dict, List, Union
from django.core.exceptions import ValidationError


def validate_pricing_tiers(value: Any) -> None:
    """Validate base pricing tiers configuration."""
    if not isinstance(value, list):
        raise ValidationError("Pricing tiers must be a list")
    
    if not value:
        raise ValidationError("At least one pricing tier is required")
    
    for i, tier in enumerate(value):
        if not isinstance(tier, dict):
            raise ValidationError(f"Tier {i+1} must be a dictionary")
        
        required_fields = ['max_distance', 'base_fee', 'per_km_rate']
        for field in required_fields:
            if field not in tier:
                raise ValidationError(f"Tier {i+1} missing required field: {field}")
        
        # Validate numeric values
        if not isinstance(tier['base_fee'], (int, float)) or tier['base_fee'] < 0:
            raise ValidationError(f"Tier {i+1} base_fee must be a positive number")
        
        if not isinstance(tier['per_km_rate'], (int, float)) or tier['per_km_rate'] < 0:
            raise ValidationError(f"Tier {i+1} per_km_rate must be a positive number")
        
        # Validate max_distance
        max_dist = tier['max_distance']
        if max_dist != 'inf' and (not isinstance(max_dist, (int, float)) or max_dist <= 0):
            raise ValidationError(f"Tier {i+1} max_distance must be a positive number or 'inf'")


def validate_peak_hours(value: Any) -> None:
    """Validate peak hours configuration."""
    if not isinstance(value, list):
        raise ValidationError("Peak hours must be a list")
    
    for i, peak in enumerate(value):
        if not isinstance(peak, dict):
            raise ValidationError(f"Peak hour {i+1} must be a dictionary")
        
        required_fields = ['start', 'end', 'multiplier', 'name']
        for field in required_fields:
            if field not in peak:
                raise ValidationError(f"Peak hour {i+1} missing required field: {field}")
        
        # Validate time format
        for time_field in ['start', 'end']:
            time_str = peak[time_field]
            if not isinstance(time_str, str):
                raise ValidationError(f"Peak hour {i+1} {time_field} must be a string")
            
            try:
                hour, minute = map(int, time_str.split(':'))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError()
            except (ValueError, AttributeError):
                raise ValidationError(f"Peak hour {i+1} {time_field} must be in HH:MM format")
        
        # Validate multiplier
        if not isinstance(peak['multiplier'], (int, float)) or peak['multiplier'] <= 0:
            raise ValidationError(f"Peak hour {i+1} multiplier must be a positive number")
        
        # Validate name
        if not isinstance(peak['name'], str) or not peak['name'].strip():
            raise ValidationError(f"Peak hour {i+1} name must be a non-empty string")


def validate_multipliers(value: Any) -> None:
    """Validate multiplier dictionaries (traffic, weather, etc.)."""
    if not isinstance(value, dict):
        raise ValidationError("Multipliers must be a dictionary")
    
    if not value:
        raise ValidationError("At least one multiplier is required")
    
    for key, multiplier in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValidationError("Multiplier keys must be non-empty strings")
        
        if not isinstance(multiplier, (int, float)) or multiplier < 0:
            raise ValidationError(f"Multiplier for '{key}' must be a non-negative number")


def validate_positive_number(value: Any) -> None:
    """Validate that a value is a positive number."""
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValidationError("Value must be a positive number")


def validate_non_negative_number(value: Any) -> None:
    """Validate that a value is a non-negative number."""
    if not isinstance(value, (int, float)) or value < 0:
        raise ValidationError("Value must be a non-negative number")


def validate_percentage(value: Any) -> None:
    """Validate that a value is a valid percentage (0-1)."""
    if not isinstance(value, (int, float)) or not (0 <= value <= 1):
        raise ValidationError("Value must be a number between 0 and 1")


def validate_cache_timeout(value: Any) -> None:
    """Validate cache timeout values."""
    if not isinstance(value, int) or value < 0:
        raise ValidationError("Cache timeout must be a non-negative integer (seconds)")
    
    if value > 86400:  # 24 hours
        raise ValidationError("Cache timeout should not exceed 24 hours (86400 seconds)")


def validate_weight_tiers(value: Any) -> None:
    """Validate weight tiers configuration."""
    if not isinstance(value, list):
        raise ValidationError("Weight tiers must be a list")
    
    for i, tier in enumerate(value):
        if not isinstance(tier, dict):
            raise ValidationError(f"Weight tier {i+1} must be a dictionary")
        
        required_fields = ['max_weight', 'surcharge']
        for field in required_fields:
            if field not in tier:
                raise ValidationError(f"Weight tier {i+1} missing required field: {field}")
        
        # Validate surcharge
        if not isinstance(tier['surcharge'], (int, float)) or tier['surcharge'] < 0:
            raise ValidationError(f"Weight tier {i+1} surcharge must be a non-negative number")
        
        # Validate max_weight
        max_weight = tier['max_weight']
        if max_weight != 'inf' and (not isinstance(max_weight, (int, float)) or max_weight <= 0):
            raise ValidationError(f"Weight tier {i+1} max_weight must be a positive number or 'inf'")


# Validation mapping for different configuration types
VALIDATION_FUNCTIONS = {
    'base_pricing_tiers': validate_pricing_tiers,
    'peak_hours': validate_peak_hours,
    'traffic_multipliers': validate_multipliers,
    'weather_multipliers': validate_multipliers,
    'rider_availability_multipliers': validate_multipliers,
    'vendor_type_multipliers': validate_multipliers,
    'loyalty_discounts': validate_multipliers,
    'weight_tiers': validate_weight_tiers,
    'max_distance_km': validate_positive_number,
    'min_delivery_fee': validate_non_negative_number,
    'max_delivery_fee': validate_positive_number,
    'base_delivery_speed_kmh': validate_positive_number,
    'preparation_time_minutes': validate_non_negative_number,
    'max_surge_multiplier': validate_positive_number,
    'free_item_threshold': validate_non_negative_number,
    'item_surcharge_per_item': validate_non_negative_number,
    'free_weight_threshold_kg': validate_non_negative_number,
    'weight_surcharge_per_kg': validate_non_negative_number,
    'route_cache_timeout': validate_cache_timeout,
    'weather_cache_timeout': validate_cache_timeout,
    'traffic_cache_timeout': validate_cache_timeout,
    'rider_cache_timeout': validate_cache_timeout,
}


def validate_configuration_value(key: str, value: Any) -> None:
    """
    Validate a configuration value based on its key.
    
    Args:
        key: Configuration key
        value: Value to validate
        
    Raises:
        ValidationError: If validation fails
    """
    validator = VALIDATION_FUNCTIONS.get(key)
    if validator:
        validator(value)


def get_validation_constraints_for_key(key: str) -> Dict[str, Any]:
    """
    Get validation constraints for a configuration key.
    
    Args:
        key: Configuration key
        
    Returns:
        Dictionary of validation constraints
    """
    constraints = {
        'validator_function': key in VALIDATION_FUNCTIONS,
        'required': True,
    }
    
    # Add specific constraints based on key
    if 'multiplier' in key or 'discount' in key:
        constraints.update({
            'min_value': 0,
            'data_type': 'float',
            'description': 'Multiplier values should be positive numbers'
        })
    elif 'timeout' in key:
        constraints.update({
            'min_value': 0,
            'max_value': 86400,
            'data_type': 'integer',
            'description': 'Timeout values in seconds (max 24 hours)'
        })
    elif 'fee' in key or 'surcharge' in key:
        constraints.update({
            'min_value': 0,
            'data_type': 'float',
            'description': 'Fee values should be non-negative numbers'
        })
    
    return constraints