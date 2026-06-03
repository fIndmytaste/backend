from django.core.management.base import BaseCommand
from helpers.models import DeliveryConfiguration
import json


class Command(BaseCommand):
    help = 'Populate delivery configuration with default values'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing configurations',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        
        # Default configuration values based on DeliveryConfig class
        default_configs = [
            # Base pricing tiers
            {
                'key': 'base_pricing_tiers',
                'category': 'pricing',
                'data_type': 'json',
                'value': json.dumps([
                    {"max_distance": 2, "base_fee": 1000, "per_km_rate": 50},
                    {"max_distance": 5, "base_fee": 1200, "per_km_rate": 80},
                    {"max_distance": 10, "base_fee": 1500, "per_km_rate": 100},
                    {"max_distance": 20, "base_fee": 2000, "per_km_rate": 120},
                    {"max_distance": "inf", "base_fee": 2500, "per_km_rate": 150}
                ]),
                'default_value': json.dumps([
                    {"max_distance": 2, "base_fee": 1000, "per_km_rate": 50},
                    {"max_distance": 5, "base_fee": 1200, "per_km_rate": 80},
                    {"max_distance": 10, "base_fee": 1500, "per_km_rate": 100},
                    {"max_distance": 20, "base_fee": 2000, "per_km_rate": 120},
                    {"max_distance": "inf", "base_fee": 2500, "per_km_rate": 150}
                ]),
                'description': 'Base pricing tiers for different distance ranges',
            },
            
            # Peak hours configuration
            {
                'key': 'peak_hours',
                'category': 'timing',
                'data_type': 'json',
                'value': json.dumps([
                    {"start": "07:00", "end": "09:30", "multiplier": 1.3, "name": "Morning Rush"},
                    {"start": "12:00", "end": "14:00", "multiplier": 1.2, "name": "Lunch Rush"},
                    {"start": "17:00", "end": "20:00", "multiplier": 1.4, "name": "Evening Rush"},
                    {"start": "22:00", "end": "23:59", "multiplier": 1.2, "name": "Late Night"}
                ]),
                'default_value': json.dumps([
                    {"start": "07:00", "end": "09:30", "multiplier": 1.3, "name": "Morning Rush"},
                    {"start": "12:00", "end": "14:00", "multiplier": 1.2, "name": "Lunch Rush"},
                    {"start": "17:00", "end": "20:00", "multiplier": 1.4, "name": "Evening Rush"},
                    {"start": "22:00", "end": "23:59", "multiplier": 1.2, "name": "Late Night"}
                ]),
                'description': 'Peak hours with surge multipliers',
            },
            
            # Traffic multipliers
            {
                'key': 'traffic_multipliers',
                'category': 'multipliers',
                'data_type': 'json',
                'value': json.dumps({
                    "free_flow": 1.0,
                    "light": 1.1,
                    "moderate": 1.3,
                    "heavy": 1.6,
                    "severe": 2.0
                }),
                'default_value': json.dumps({
                    "free_flow": 1.0,
                    "light": 1.1,
                    "moderate": 1.3,
                    "heavy": 1.6,
                    "severe": 2.0
                }),
                'description': 'Traffic condition multipliers',
            },
            
            # Weather multipliers
            {
                'key': 'weather_multipliers',
                'category': 'multipliers',
                'data_type': 'json',
                'value': json.dumps({
                    "clear": 1.0,
                    "cloudy": 1.0,
                    "light_rain": 1.2,
                    "heavy_rain": 1.5,
                    "thunderstorm": 1.8,
                    "fog": 1.3,
                    "snow": 2.0
                }),
                'default_value': json.dumps({
                    "clear": 1.0,
                    "cloudy": 1.0,
                    "light_rain": 1.2,
                    "heavy_rain": 1.5,
                    "thunderstorm": 1.8,
                    "fog": 1.3,
                    "snow": 2.0
                }),
                'description': 'Weather condition multipliers',
            },
            
            # Rider availability multipliers
            {
                'key': 'rider_availability_multipliers',
                'category': 'multipliers',
                'data_type': 'json',
                'value': json.dumps({
                    "high": 0.9,
                    "normal": 1.0,
                    "low": 1.3,
                    "critical": 1.8
                }),
                'default_value': json.dumps({
                    "high": 0.9,
                    "normal": 1.0,
                    "low": 1.3,
                    "critical": 1.8
                }),
                'description': 'Rider availability multipliers',
            },
            
            # Vendor type multipliers
            {
                'key': 'vendor_type_multipliers',
                'category': 'multipliers',
                'data_type': 'json',
                'value': json.dumps({
                    "restaurant": 1.0,
                    "grocery": 1.1,
                    "pharmacy": 1.2,
                    "electronics": 1.3,
                    "fragile_items": 1.5
                }),
                'default_value': json.dumps({
                    "restaurant": 1.0,
                    "grocery": 1.1,
                    "pharmacy": 1.2,
                    "electronics": 1.3,
                    "fragile_items": 1.5
                }),
                'description': 'Vendor type multipliers',
            },
            
            # Loyalty discounts
            {
                'key': 'loyalty_discounts',
                'category': 'multipliers',
                'data_type': 'json',
                'value': json.dumps({
                    "bronze": 0.05,
                    "silver": 0.10,
                    "gold": 0.15,
                    "platinum": 0.20
                }),
                'default_value': json.dumps({
                    "bronze": 0.05,
                    "silver": 0.10,
                    "gold": 0.15,
                    "platinum": 0.20
                }),
                'description': 'Loyalty tier discounts',
            },
            
            # Basic thresholds and limits
            {
                'key': 'max_distance_km',
                'category': 'thresholds',
                'data_type': 'int',
                'value': '50',
                'default_value': '50',
                'description': 'Maximum delivery distance in kilometers',
                'min_value': 1,
                'max_value': 200,
            },
            {
                'key': 'min_delivery_fee',
                'category': 'pricing',
                'data_type': 'int',
                'value': '500',
                'default_value': '500',
                'description': 'Minimum delivery fee in NGN',
                'min_value': 100,
                'max_value': 2000,
            },
            {
                'key': 'rider_minimum_withdrawal',
                'category': 'thresholds',
                'data_type': 'int',
                'value': '10000',
                'default_value': '10000',
                'description': 'Minimum rider wallet withdrawal amount in NGN',
                'min_value': 0,
                'max_value': 1000000,
            },
            {
                'key': 'vendor_minimum_withdrawal',
                'category': 'thresholds',
                'data_type': 'int',
                'value': '30000',
                'default_value': '30000',
                'description': 'Minimum vendor wallet withdrawal amount in NGN',
                'min_value': 0,
                'max_value': 1000000,
            },
            {
                'key': 'max_delivery_fee',
                'category': 'pricing',
                'data_type': 'int',
                'value': '10000',
                'default_value': '10000',
                'description': 'Maximum delivery fee in NGN',
                'min_value': 1000,
                'max_value': 50000,
            },
            {
                'key': 'base_delivery_speed_kmh',
                'category': 'timing',
                'data_type': 'int',
                'value': '25',
                'default_value': '25',
                'description': 'Average delivery speed in km/h',
                'min_value': 10,
                'max_value': 60,
            },
            {
                'key': 'preparation_time_minutes',
                'category': 'timing',
                'data_type': 'int',
                'value': '15',
                'default_value': '15',
                'description': 'Order preparation time in minutes',
                'min_value': 5,
                'max_value': 60,
            },
            {
                'key': 'max_surge_multiplier',
                'category': 'multipliers',
                'data_type': 'float',
                'value': '3.0',
                'default_value': '3.0',
                'description': 'Maximum surge pricing multiplier',
                'min_value': 1.0,
                'max_value': 5.0,
            },
            
            # Item and weight surcharges
            {
                'key': 'free_item_threshold',
                'category': 'thresholds',
                'data_type': 'int',
                'value': '1',
                'default_value': '1',
                'description': 'Number of free items before surcharge',
                'min_value': 1,
                'max_value': 10,
            },
            {
                'key': 'item_surcharge_per_item',
                'category': 'pricing',
                'data_type': 'float',
                'value': '50.0',
                'default_value': '50.0',
                'description': 'Surcharge per additional item in NGN',
                'min_value': 0,
                'max_value': 500,
            },
            {
                'key': 'free_weight_threshold_kg',
                'category': 'thresholds',
                'data_type': 'float',
                'value': '2.0',
                'default_value': '2.0',
                'description': 'Free weight limit in kg',
                'min_value': 0.5,
                'max_value': 20.0,
            },
            {
                'key': 'weight_surcharge_per_kg',
                'category': 'pricing',
                'data_type': 'float',
                'value': '100.0',
                'default_value': '100.0',
                'description': 'Surcharge per additional kg in NGN',
                'min_value': 0,
                'max_value': 1000,
            },
            
            # Cache timeouts
            {
                'key': 'route_cache_timeout',
                'category': 'cache',
                'data_type': 'int',
                'value': '1800',
                'default_value': '1800',
                'description': 'Route cache timeout in seconds',
                'min_value': 60,
                'max_value': 7200,
            },
            {
                'key': 'weather_cache_timeout',
                'category': 'cache',
                'data_type': 'int',
                'value': '600',
                'default_value': '600',
                'description': 'Weather cache timeout in seconds',
                'min_value': 60,
                'max_value': 3600,
            },
            {
                'key': 'traffic_cache_timeout',
                'category': 'cache',
                'data_type': 'int',
                'value': '180',
                'default_value': '180',
                'description': 'Traffic cache timeout in seconds',
                'min_value': 30,
                'max_value': 1800,
            },
            {
                'key': 'rider_cache_timeout',
                'category': 'cache',
                'data_type': 'int',
                'value': '120',
                'default_value': '120',
                'description': 'Rider availability cache timeout in seconds',
                'min_value': 30,
                'max_value': 600,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for config_data in default_configs:
            key = config_data['key']
            
            try:
                config = DeliveryConfiguration.objects.get(key=key)
                if overwrite:
                    for field, value in config_data.items():
                        if field != 'key':
                            setattr(config, field, value)
                    config.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated configuration: {key}')
                    )
                else:
                    self.stdout.write(
                        self.style.NOTICE(f'Configuration already exists: {key} (use --overwrite to update)')
                    )
            except DeliveryConfiguration.DoesNotExist:
                DeliveryConfiguration.objects.create(**config_data)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created configuration: {key}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! Created: {created_count}, Updated: {updated_count}'
            )
        )
