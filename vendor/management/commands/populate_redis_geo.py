"""
Management command: populate_redis_geo

Rebuilds the Redis geo index ("vendors:geo") from the database.
Run this once on first deploy. After that, vendor saves keep it in sync
automatically via the post_save signal in vendor/signals.py.

Usage:
    python manage.py populate_redis_geo
"""

from django.core.management.base import BaseCommand
from django.conf import settings

from account.models import Vendor


class Command(BaseCommand):
    help = 'Rebuild the Redis geo index for vendor proximity queries.'

    def handle(self, *args, **kwargs):
        try:
            import redis as redis_lib
        except ImportError:
            self.stderr.write(self.style.ERROR('redis-py is not installed. Run: pip install redis'))
            return

        location = settings.CACHES.get('default', {}).get('LOCATION')
        if not location:
            self.stderr.write(self.style.ERROR('No Redis LOCATION found in CACHES["default"]. Check settings.'))
            return

        try:
            r = redis_lib.Redis.from_url(location, socket_connect_timeout=5)
            r.ping()
            self.stdout.write(self.style.SUCCESS('Connected to Redis.'))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Cannot connect to Redis: {exc}'))
            return

        # Only index vendors that should be discoverable:
        # approved, active, and with valid coordinates.
        vendors = Vendor.objects.filter(
            approval_status='approved',
            is_active=True,
            location_latitude__isnull=False,
            location_longitude__isnull=False,
        ).exclude(
            location_latitude='',
            location_longitude='',
        )

        total = vendors.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No eligible vendors found. Index not changed.'))
            return

        self.stdout.write(f'Indexing {total} vendors...')

        # Rebuild atomically: delete old key, pipeline all GEOADDs, execute at once.
        pipe = r.pipeline()
        pipe.delete('vendors:geo')

        added = 0
        skipped = 0
        for vendor in vendors.iterator():
            try:
                lon = float(vendor.location_longitude)
                lat = float(vendor.location_latitude)
            except (TypeError, ValueError):
                self.stdout.write(
                    self.style.WARNING(f'  Skipped {vendor.id} ({vendor.name}): invalid coordinates.')
                )
                skipped += 1
                continue

            pipe.execute_command('GEOADD', 'vendors:geo', lon, lat, str(vendor.id))
            added += 1

        pipe.execute()

        count = r.zcard('vendors:geo')
        self.stdout.write(self.style.SUCCESS(
            f'\nDone. {added} vendors indexed, {skipped} skipped. '
            f'Redis "vendors:geo" now has {count} entries.'
        ))
