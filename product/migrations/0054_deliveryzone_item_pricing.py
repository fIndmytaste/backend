# Generated manually on 2026-05-12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0053_bukavariantservicecharge"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliveryzone",
            name="second_item_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=0.00,
                help_text="Extra delivery fee for the second item in this zone.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="deliveryzone",
            name="additional_item_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=0.00,
                help_text="Extra delivery fee per item from the third item onwards in this zone.",
                max_digits=10,
            ),
        ),
    ]
