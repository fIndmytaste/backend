"""
Management command: populate_rider_redis_geo

Rebuilds the Redis geo index for online riders from the database.

Usage:
    python manage.py populate_rider_redis_geo
"""

from django.core.management.base import BaseCommand

from account.models import Rider
from helpers.redis_rider_geo import rebuild_rider_geo_index
from helpers.redis_geo import _get_redis_client


class Command(BaseCommand):
    help = "Rebuild the Redis geo index for rider dispatch proximity queries."

    def handle(self, *args, **kwargs):
        client = _get_redis_client()
        if client is None:
            self.stderr.write(
                self.style.ERROR('Cannot connect to Redis. Check CACHES["default"]["LOCATION"].')
            )
            return

        riders = Rider.objects.filter(
            status='active',
            is_verified=True,
            is_online=True,
        )

        total = riders.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No eligible riders found. Index not changed."))
            return

        indexed, skipped = rebuild_rider_geo_index(riders.iterator())
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {indexed} riders indexed, {skipped} skipped. "
                f'Redis "riders:geo" now has {client.zcard("riders:geo")} entries.'
            )
        )
