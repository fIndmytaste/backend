from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.cache import cache
from django.core.exceptions import ValidationError
import json
import logging

logger = logging.getLogger(__name__)

# Import validation functions
try:
    from .validators import validate_configuration_value, get_validation_constraints_for_key
except ImportError:
    # Fallback if validators module is not available
    def validate_configuration_value(key, value):
        pass
    
    def get_validation_constraints_for_key(key):
        return {}


class DeliveryConfiguration(models.Model):
    """
    Dynamic configuration for delivery pricing parameters.
    Allows administrators to adjust pricing without code changes.
    """
    
    # Configuration categories
    CATEGORY_CHOICES = [
        ('pricing', 'Pricing'),
        ('timing', 'Timing'),
        ('multipliers', 'Multipliers'),
        ('thresholds', 'Thresholds'),
        ('cache', 'Cache Settings'),
    ]
    
    # Data types
    DATA_TYPE_CHOICES = [
        ('float', 'Float'),
        ('int', 'Integer'),
        ('json', 'JSON'),
        ('bool', 'Boolean'),
        ('string', 'String'),
    ]
    
    key = models.CharField(max_length=100, unique=True, help_text="Configuration key (e.g., 'base_fee_tier_1')")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='pricing')
    data_type = models.CharField(max_length=10, choices=DATA_TYPE_CHOICES, default='float')
    value = models.TextField(help_text="Configuration value (JSON for complex types)")
    default_value = models.TextField(help_text="Default fallback value")
    description = models.TextField(help_text="Description of what this configuration controls")
    
    # Validation constraints
    min_value = models.FloatField(null=True, blank=True, help_text="Minimum allowed value (for numeric types)")
    max_value = models.FloatField(null=True, blank=True, help_text="Maximum allowed value (for numeric types)")
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True, help_text="User who last updated this config")
    
    class Meta:
        db_table = 'delivery_configuration'
        ordering = ['category', 'key']
        verbose_name = 'Delivery Configuration'
        verbose_name_plural = 'Delivery Configurations'
    
    def __str__(self):
        return f"{self.category}.{self.key}"
    
    def get_typed_value(self):
        """Return the value converted to the appropriate Python type."""
        try:
            if self.data_type == 'int':
                return int(self.value)
            elif self.data_type == 'float':
                return float(self.value)
            elif self.data_type == 'bool':
                return self.value.lower() in ('true', '1', 'yes', 'on')
            elif self.data_type == 'json':
                return json.loads(self.value)
            else:  # string
                return self.value
        except (ValueError, json.JSONDecodeError):
            # Return default value if conversion fails
            return self.get_default_value()
    
    def get_default_value(self):
        """Return the default value converted to the appropriate Python type."""
        try:
            if self.data_type == 'int':
                return int(self.default_value)
            elif self.data_type == 'float':
                return float(self.default_value)
            elif self.data_type == 'bool':
                return self.default_value.lower() in ('true', '1', 'yes', 'on')
            elif self.data_type == 'json':
                return json.loads(self.default_value)
            else:  # string
                return self.default_value
        except (ValueError, json.JSONDecodeError):
            return None
    
    def clean(self):
        """Validate the configuration value based on its data type and key-specific rules."""
        super().clean()
        
        # Validate that the value can be converted to the specified data type
        try:
            typed_value = self.get_typed_value()
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise ValidationError(f"Invalid value for data type '{self.data_type}': {e}")
        
        # Apply key-specific validation
        try:
            validate_configuration_value(self.key, typed_value)
        except ValidationError as e:
            raise ValidationError(f"Configuration validation failed for '{self.key}': {e}")
        
        # Validate numeric ranges
        if self.data_type in ['int', 'float'] and typed_value is not None:
            if self.min_value is not None and typed_value < self.min_value:
                raise ValidationError(f"Value {typed_value} is below minimum {self.min_value}")
            if self.max_value is not None and typed_value > self.max_value:
                raise ValidationError(f"Value {typed_value} is above maximum {self.max_value}")
    
    def auto_populate_constraints(self):
        """Auto-populate validation constraints based on the configuration key."""
        if not hasattr(self, 'validation_constraints') or not self.validation_constraints:
            constraints = get_validation_constraints_for_key(self.key)
            if constraints:
                if hasattr(self, 'validation_constraints'):
                    self.validation_constraints = json.dumps(constraints)
    
    def save(self, *args, **kwargs):
        """Auto-populate constraints and clear cache when configuration is saved."""
        # Auto-populate validation constraints if not set
        self.auto_populate_constraints()
        
        # Validate before saving
        self.full_clean()
        
        super().save(*args, **kwargs)
        
        # Clear the configuration cache
        cache.delete('delivery_config_cache')
        cache.delete(f'delivery_config_{self.key}')
        
        logger.info(f"Configuration '{self.key}' updated with value: {self.value}")


class ConfigurationManager:
    """
    Manager class for handling delivery configuration with caching.
    """
    
    CACHE_KEY = 'delivery_config_cache'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    @classmethod
    def get_config(cls, key: str, default=None):
        """
        Get a configuration value by key with caching.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        # Try individual cache first
        cache_key = f'delivery_config_{key}'
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value
        
        # Try database
        try:
            config = DeliveryConfiguration.objects.get(key=key, is_active=True)
            value = config.get_typed_value()
            
            # Cache the value
            cache.set(cache_key, value, cls.CACHE_TIMEOUT)
            return value
            
        except DeliveryConfiguration.DoesNotExist:
            return default
    
    @classmethod
    def get_all_configs(cls):
        """
        Get all active configurations as a dictionary with caching.
        
        Returns:
            Dictionary of all configuration key-value pairs
        """
        cached_configs = cache.get(cls.CACHE_KEY)
        if cached_configs is not None:
            return cached_configs
        
        # Build config dictionary from database
        configs = {}
        for config in DeliveryConfiguration.objects.filter(is_active=True):
            configs[config.key] = config.get_typed_value()
        
        # Cache the full config dictionary
        cache.set(cls.CACHE_KEY, configs, cls.CACHE_TIMEOUT)
        return configs
    
    @classmethod
    def refresh_cache(cls):
        """Force refresh of configuration cache."""
        cache.delete(cls.CACHE_KEY)
        # Delete individual config caches
        for config in DeliveryConfiguration.objects.filter(is_active=True):
            cache.delete(f'delivery_config_{config.key}')
        
        # Rebuild cache
        return cls.get_all_configs()
    
    @classmethod
    def set_config(cls, key: str, value, user: str = None):
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: New value
            user: User making the change
        """
        try:
            config = DeliveryConfiguration.objects.get(key=key)
            
            # Convert value to string for storage
            if isinstance(value, (dict, list)):
                config.value = json.dumps(value)
            else:
                config.value = str(value)
            
            if user:
                config.updated_by = user
            
            config.save()
            return True
            
        except DeliveryConfiguration.DoesNotExist:
            return False
