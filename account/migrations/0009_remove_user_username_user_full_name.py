# Generated by Django 5.1.5 on 2025-03-07 22:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0008_address_is_primary'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='username',
        ),
        migrations.AddField(
            model_name='user',
            name='full_name',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
