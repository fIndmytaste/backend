"""Find (and optionally delete) role-profile rows created by wrong-app logins.

Background: UserSerializer.to_representation used to call get_or_create() on the
read path, so signing a rider into the vendor app minted an empty Vendor row for
that rider (and vice versa). The vendor app then read the blank row as a
half-finished onboarding and showed "Continue Registration" forever.

The serializer no longer does that, but rows created before the fix are still
there. This command reports them, and only deletes with --delete.

    python manage.py audit_role_mismatched_profiles
    python manage.py audit_role_mismatched_profiles --delete
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from account.models import Rider, User, Vendor


# Fields that indicate a human actually filled the record in. If every one of
# these is blank, the row carries no data worth keeping.
VENDOR_DATA_FIELDS = (
    'name', 'address', 'location_latitude', 'location_longitude',
    'description', 'thumbnail_url', 'logo_url', 'phone_number',
    'country', 'state', 'city',
)
RIDER_DATA_FIELDS = (
    'mode_of_transport', 'vehicle_number', 'vehicle_brand', 'plate_number',
    'next_of_kin', 'next_of_kin_phone', 'preferred_location',
)


def _is_blank(value):
    return value is None or str(value).strip() == ''


def _has_data(obj, fields):
    return any(not _is_blank(getattr(obj, f, None)) for f in fields)


def _related_counts(obj):
    """Count rows pointing at ``obj`` so we never delete something in use."""
    counts = {}
    for rel in obj._meta.related_objects:
        accessor = rel.get_accessor_name()
        try:
            manager = getattr(obj, accessor)
        except Exception:
            continue
        if hasattr(manager, 'count'):
            n = manager.count()
        else:
            n = 1 if manager is not None else 0
        if n:
            counts[accessor] = n
    return counts


class Command(BaseCommand):
    help = "Report role/profile mismatches left behind by wrong-app logins."

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete the empty, unreferenced mismatched rows.',
        )

    def handle(self, *args, **options):
        do_delete = options['delete']
        deletable, skipped = [], []

        checks = (
            ('Vendor', Vendor, 'vendor', VENDOR_DATA_FIELDS),
            ('Rider', Rider, 'rider', RIDER_DATA_FIELDS),
        )

        for label, model, expected_role, data_fields in checks:
            qs = model.objects.exclude(user__role=expected_role).select_related('user')
            for obj in qs:
                user = obj.user
                entry = (label, obj, user)
                reasons = []
                if _has_data(obj, data_fields):
                    reasons.append('record has data')
                related = _related_counts(obj)
                if related:
                    reasons.append(
                        'referenced by ' + ', '.join(
                            f'{k}={v}' for k, v in sorted(related.items())
                        )
                    )
                if reasons:
                    skipped.append(entry + ('; '.join(reasons),))
                else:
                    deletable.append(entry)

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nRole/profile mismatches\n'
        ))

        if not deletable and not skipped:
            self.stdout.write(self.style.SUCCESS('None found. Nothing to do.'))
            return

        if deletable:
            self.stdout.write(self.style.WARNING(
                f'Empty and unreferenced ({len(deletable)}) '
                '- safe to remove:'
            ))
            for label, obj, user in deletable:
                self.stdout.write(
                    f'  {label} {obj.pk}  user={user.email}  role={user.role}'
                )

        if skipped:
            self.stdout.write(self.style.WARNING(
                f'\nNeeds a human ({len(skipped)}) '
                '- NOT deletable, review by hand:'
            ))
            for label, obj, user, reason in skipped:
                self.stdout.write(
                    f'  {label} {obj.pk}  user={user.email}  '
                    f'role={user.role}  ({reason})'
                )

        if not do_delete:
            self.stdout.write(
                '\nDry run. Re-run with --delete to remove the safe rows.'
            )
            return

        if not deletable:
            self.stdout.write('\nNothing safe to delete.')
            return

        with transaction.atomic():
            for label, obj, user in deletable:
                obj.delete()

        self.stdout.write(self.style.SUCCESS(
            f'\nDeleted {len(deletable)} empty mismatched row(s).'
        ))
