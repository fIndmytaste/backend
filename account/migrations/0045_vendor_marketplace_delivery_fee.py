from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0044_alter_vendor_close_time_alter_vendor_open_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendor',
            name='marketplace_delivery_fee',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Override base delivery fee for this vendor when in a marketplace. Leave blank to use marketplace default.',
                max_digits=10,
                null=True,
            ),
        ),
    ]
