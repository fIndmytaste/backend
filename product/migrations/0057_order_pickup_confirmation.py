from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0056_promocode_referrer_discounted_delivery'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='pickup_confirmed_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp when marketplace pickup was confirmed.', null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='pickup_confirmed_by',
            field=models.ForeignKey(blank=True, help_text='Marketplace staff/admin user who confirmed item pickup.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_marketplace_pickups', to=settings.AUTH_USER_MODEL),
        ),
    ]
