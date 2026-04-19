"""
Management command: cleanup_rider_redis_geo

Removes stale riders from the Redis rider geo index using the freshness set.

Usage:
    python manage.py cleanup_rider_redis_geo
    python manage.py cleanup_rider_redis_geo --max-age-seconds 180
"""

from django.core.management.base import BaseCommand

from helpers.redis_rider_geo import cleanup_stale_riders


class Command(BaseCommand):
    help = "Remove stale riders from the Redis rider geo index."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-seconds",
            type=int,
            default=120,
            help="Maximum age in seconds before a rider is considered stale.",
        )

    def handle(self, *args, **options):
        removed = cleanup_stale_riders(max_age_seconds=options["max_age_seconds"])
        self.stdout.write(
            self.style.SUCCESS(f"Removed {removed} stale riders from Redis geo index.")
        )
