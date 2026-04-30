from decimal import Decimal

from django.core.management.base import BaseCommand

from product.models import DeliveryZone


def box(center_lat, center_lng, lat_radius=0.012, lng_radius=0.012):
    return [
        [center_lat - lat_radius, center_lng - lng_radius],
        [center_lat - lat_radius, center_lng + lng_radius],
        [center_lat + lat_radius, center_lng + lng_radius],
        [center_lat + lat_radius, center_lng - lng_radius],
        [center_lat - lat_radius, center_lng - lng_radius],
    ]


MARKETPLACE_ZONES = [
    ("Lagos Island (Sura)", 6.4590, 3.3950, 0.010, 0.010),
    ("Lagos Island (TBS)", 6.4470, 3.4040, 0.010, 0.010),
    ("Lagos Island (Onikan)", 6.4475, 3.4160, 0.010, 0.010),
    ("Victoria Island (Adeola Odeku)", 6.4305, 3.4210, 0.011, 0.012),
    ("Victoria Island (Kofo Abayomi)", 6.4365, 3.4285, 0.011, 0.012),
    ("Ikoyi (Dolphin)", 6.4560, 3.4210, 0.012, 0.012),
    ("Ikoyi (Glover Road)", 6.4515, 3.4380, 0.012, 0.012),
    ("Lekki (VGC)", 6.4690, 3.5880, 0.018, 0.018),
    ("Lekki Phase 1 (Admiralty Road)", 6.4470, 3.4720, 0.016, 0.018),
    ("Lekki Phase 1 (Fola Osibo)", 6.4400, 3.4660, 0.014, 0.014),
    ("Ajah (Abraham Adesanya)", 6.4690, 3.6310, 0.018, 0.018),
    ("Ajah (Badore)", 6.5100, 3.6100, 0.020, 0.020),
    ("Apapa (GRA)", 6.4450, 3.3610, 0.016, 0.016),
    ("Apapa (Kiri Kiri)", 6.4570, 3.3380, 0.016, 0.016),
    ("Apapa (Olodi)", 6.4620, 3.3500, 0.016, 0.016),
    ("Apapa (Tin Can)", 6.4400, 3.3400, 0.018, 0.018),
    ("Surulere", 6.5000, 3.3530, 0.026, 0.026),
    ("Yaba", 6.5150, 3.3880, 0.022, 0.024),
    ("Ikeja", 6.6050, 3.3490, 0.030, 0.030),
    ("Maryland (Mende)", 6.5720, 3.3700, 0.014, 0.014),
    ("Maryland (Onigbongbo)", 6.5810, 3.3650, 0.014, 0.014),
    ("Ojodu", 6.6420, 3.3520, 0.022, 0.022),
    ("Agege (Dopemu)", 6.6240, 3.3140, 0.018, 0.018),
    ("Agege (Iju Road)", 6.6510, 3.3340, 0.020, 0.020),
    ("Agege (Orile Agege)", 6.6330, 3.3220, 0.018, 0.018),
    ("Egbeda", 6.5960, 3.2960, 0.024, 0.024),
    ("Ikorodu (Owode-Ibese)", 6.6280, 3.5220, 0.020, 0.020),
    ("Ikorodu (Owode Onirin)", 6.5990, 3.5040, 0.020, 0.020),
    ("Ikorodu (Ogolonto)", 6.6170, 3.5070, 0.018, 0.018),
    ("Ikorodu (Sabo)", 6.6190, 3.5100, 0.018, 0.018),
    ("Festac Town", 6.4680, 3.2830, 0.026, 0.026),
    ("Amuwo Odofin", 6.4630, 3.2800, 0.030, 0.030),
]


class Command(BaseCommand):
    help = "Seed initial marketplace delivery zones for Lagos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--default-fee",
            default="1500.00",
            help="Fixed delivery fee to use for created zones.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update boundaries and fixed fees for zones that already exist.",
        )

    def handle(self, *args, **options):
        fixed_fee = Decimal(str(options["default_fee"]))
        update_existing = options["update_existing"]
        created_count = 0
        updated_count = 0

        for name, lat, lng, lat_radius, lng_radius in MARKETPLACE_ZONES:
            boundary = box(lat, lng, lat_radius, lng_radius)
            zone, created = DeliveryZone.objects.get_or_create(
                name=name,
                defaults={
                    "boundary": boundary,
                    "fixed_fee": fixed_fee,
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                continue

            if update_existing:
                zone.boundary = boundary
                zone.fixed_fee = fixed_fee
                zone.is_active = True
                zone.save(update_fields=["boundary", "fixed_fee", "is_active", "updated_at"])
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Marketplace delivery zones ready. Created: {created_count}. Updated: {updated_count}."
            )
        )
