from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0048_staffpagepermission_push_notifications'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staffpagepermission',
            name='page',
            field=models.CharField(choices=[
                ('overview', 'Overview'),
                ('orders', 'Order Management'),
                ('promo-orders', 'Promo Orders'),
                ('vendor', 'Vendor Management'),
                ('riders', 'Rider Management'),
                ('rider-verification', 'Rider Verification'),
                ('customer', 'Customer Management'),
                ('insights', 'Insights'),
                ('marketplace', 'Marketplace Management'),
                ('transactions', 'Transactions'),
                ('push-notifications', 'Push Notifications'),
            ], max_length=40),
        ),
    ]
