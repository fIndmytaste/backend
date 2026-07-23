from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0058_product_creation_lock'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='platform_marketplace_delivery_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    'Marketplace delivery fee retained by the platform. Null '
                    'means the financial snapshot predates this field.'
                ),
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='rider_commission_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    'Platform commission retained from the rider fare. Null '
                    'for legacy/unfinalized orders.'
                ),
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='rider_commission_percentage_applied',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    'Rider commission percentage captured when the delivery '
                    'was completed.'
                ),
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='rider_gross_earning',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    'Gross rider fare before platform commission. Null for '
                    'legacy/unfinalized orders.'
                ),
                max_digits=10,
                null=True,
            ),
        ),
    ]
