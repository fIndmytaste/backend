from django.urls import reverse
from rest_framework.test import APITestCase

from account.models import User
from product.models import Order


class AdminDashboardOverviewTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='overview-admin@example.com',
            password='password',
        )
        self.customer = User.objects.create_user(
            email='overview-customer@example.com',
            password='password',
        )
        self.client.force_authenticate(self.admin)

    def create_order(self, **overrides):
        values = {
            'user': self.customer,
            'payment_status': 'paid',
            'status': 'delivered',
            'delivery_status': 'delivered',
            'total_amount': 1000,
            'vendor_amount': 700,
            'rider_earning': 150,
            'platform_amount': 300,
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def test_revenue_summary_includes_final_rider_and_platform_amounts(self):
        self.create_order()
        self.create_order(
            status='in_transit',
            delivery_status='in_transit',
            rider_earning=999,
            platform_amount=50,
        )
        self.create_order(
            payment_status='pending',
            rider_earning=500,
            platform_amount=500,
        )

        response = self.client.get(
            reverse('dashboard-overview'),
            {'period': 'week'},
        )

        self.assertEqual(response.status_code, 200)
        summary = response.data['data']['revenue_summary']
        self.assertEqual(summary['rider_payouts']['value'], 150.0)
        self.assertEqual(summary['platform_earnings']['value'], 350.0)
