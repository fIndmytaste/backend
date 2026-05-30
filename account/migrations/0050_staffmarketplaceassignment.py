from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('vendor', '0003_marketplace_additional_item_fee_and_more'),
        ('account', '0049_staffpagepermission_promo_orders'),
    ]

    operations = [
        migrations.CreateModel(
            name='StaffMarketplaceAssignment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_marketplace_staff', to=settings.AUTH_USER_MODEL)),
                ('marketplace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_assignments', to='vendor.marketplace')),
                ('user', models.ForeignKey(limit_choices_to={'is_staff': True}, on_delete=django.db.models.deletion.CASCADE, related_name='marketplace_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Staff Marketplace Assignment',
                'verbose_name_plural': 'Staff Marketplace Assignments',
                'ordering': ['user__email', 'marketplace__name'],
                'unique_together': {('user', 'marketplace')},
            },
        ),
    ]
