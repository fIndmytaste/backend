# Generated by Django 5.1.5 on 2025-02-15 21:22

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0008_address_is_primary'),
        ('product', '0004_productimage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='vendor',
            field=models.ForeignKey(blank=True, help_text='The vendor who owns the order.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vendors', to='account.vendor'),
        ),
        migrations.AlterField(
            model_name='order',
            name='user',
            field=models.ForeignKey(blank=True, help_text='The user who placed the order.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to=settings.AUTH_USER_MODEL),
        ),
    ]
