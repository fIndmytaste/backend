# Generated by Django 5.1.5 on 2025-02-15 21:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0007_vendor_close_day_vendor_close_time_vendor_open_day_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='is_primary',
            field=models.BooleanField(default=False),
        ),
    ]
