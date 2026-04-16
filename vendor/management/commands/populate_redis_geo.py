# management/commands/populate_redis_geo.py
from django.core.management.base import BaseCommand
from account.models import User, Vendor
import redis
from django.conf import settings

class Command(BaseCommand):
    help = 'Populate Redis with vendor geospatial data for location-based queries'

    def handle(self, *args, **kwargs):
        try:
            # Get Redis connection
            if 'LOCATION' in settings.CACHES['default']:
                r = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])
            else:
                self.stdout.write(self.style.ERROR('Redis not configured. Please check your settings.'))
                return

            # Test Redis connection
            r.ping()
            self.stdout.write(self.style.SUCCESS('✅ Connected to Redis successfully'))

            # Get all vendors with location data and approved status
            vendors = Vendor.objects.filter(
                location_latitude__isnull=False,
                location_longitude__isnull=False,
                approval_status='approved'
            )

            if not vendors.exists():
                self.stdout.write(self.style.WARNING('No approved vendors with location data found.'))
                return

            # Clear existing vendor geo data
            r.delete("vendors:geo")
            self.stdout.write(self.style.SUCCESS('Cleared existing vendor geo data'))

            # Populate Redis with vendor locations
            added_count = 0
            for vendor in vendors:
                try:
                    longitude = float(vendor.location_longitude)
                    latitude = float(vendor.location_latitude)
                    
                    # Add vendor to Redis geospatial index using execute_command
                    # Format: GEOADD key longitude latitude member
                    result = r.execute_command("GEOADD", "vendors:geo", longitude, latitude, str(vendor.id))
                    
                    if result:
                        added_count += 1
                        self.stdout.write(f'Added vendor {vendor.id}: {vendor.name} at ({longitude}, {latitude})')
                    
                except (ValueError, TypeError) as e:
                    self.stdout.write(
                        self.style.WARNING(f'Skipped vendor {vendor.id}: Invalid coordinates - {e}')
                    )
                    continue

            self.stdout.write(
                self.style.SUCCESS(f'✅ Successfully populated Redis with {added_count} vendors!')
            )

            # Verify the data
            total_vendors = r.zcard("vendors:geo")
            self.stdout.write(
                self.style.SUCCESS(f'✅ Redis now contains {total_vendors} vendors in geospatial index')
            )

        except redis.ConnectionError:
            self.stdout.write(
                self.style.ERROR('❌ Failed to connect to Redis. Please check your Redis configuration.')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error populating Redis: {e}')
            )