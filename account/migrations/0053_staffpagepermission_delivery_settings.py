from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0052_staffpagepermission_marketplace_staff_pricing'),
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
                ('marketplace-staff', 'Marketplace Staff (limited)'),
                ('transactions', 'Transactions'),
                ('push-notifications', 'Push Notifications'),
                ('pricing', 'Pricing'),
                ('delivery-settings', 'Delivery Settings'),
            ], max_length=40),
        ),
    ]
