# Generated manually on 2026-05-18

from django.db import migrations, models


def mark_existing_stocked_variants_as_tracked(apps, schema_editor):
    ProductVariant = apps.get_model("product", "ProductVariant")
    ProductVariant.objects.filter(stock__gt=0).update(track_stock=True)


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0054_deliveryzone_item_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="track_stock",
            field=models.BooleanField(
                default=False,
                help_text="When enabled, this variant option is blocked at checkout if stock is 0.",
            ),
        ),
        migrations.RunPython(mark_existing_stocked_variants_as_tracked, migrations.RunPython.noop),
    ]
