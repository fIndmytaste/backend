# Generated by Django 5.1.5 on 2025-04-28 20:25

import cloudinary.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_user_profile_image_alter_rider_drivers_license_back_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendor',
            name='thumbnail',
            field=cloudinary.models.CloudinaryField(blank=True, max_length=255, null=True, verbose_name='vendor_images'),
        ),
    ]
