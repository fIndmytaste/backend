from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0047_alter_order_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsettings',
            name='rider_commission_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text=(
                    'Platform commission deducted from rider delivery fee before crediting '
                    'the rider. E.g. 10.00 means rider keeps 90% of the delivery fee. '
                    'Set to 0 to disable.'
                ),
                max_digits=5,
            ),
        ),
    ]
