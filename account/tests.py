from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from account.models import Rider, User, Vendor


@patch('account.views.auth.emailService.send_verification_code')
class RoleProfileOnSignupTests(APITestCase):
    """Rider signup shares RegisterVendorSerializer; only vendors get a Vendor row."""

    def _signup(self, url_name, email):
        return self.client.post(reverse(url_name), {
            'full_name': 'Test Person',
            'phone_number': '08012345678',
            'email': email,
            'password': 'a-strong-password',
        })

    def test_rider_signup_creates_rider_but_no_vendor(self, _send):
        response = self._signup('rider-register', 'new-rider@example.com')

        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(email='new-rider@example.com')
        self.assertEqual(user.role, 'rider')
        self.assertTrue(Rider.objects.filter(user=user).exists())
        self.assertFalse(Vendor.objects.filter(user=user).exists())

    def test_vendor_signup_creates_vendor(self, _send):
        response = self._signup('vendor-register', 'new-vendor@example.com')

        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(email='new-vendor@example.com')
        self.assertEqual(user.role, 'vendor')
        self.assertTrue(Vendor.objects.filter(user=user).exists())
        self.assertFalse(Rider.objects.filter(user=user).exists())


class ThumbnailUploadTests(APITestCase):
    def test_rider_cannot_create_a_vendor_by_uploading_a_thumbnail(self):
        rider = User.objects.create_user(email='thumb-rider@example.com', password='password', role='rider')
        self.client.force_authenticate(rider)

        response = self.client.patch(
            reverse('ProfileImageUploadView'),
            {'thumbnail': SimpleUploadedFile('t.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Vendor.objects.filter(user=rider).exists())


class AdminVendorListExcludesRidersTests(APITestCase):
    def test_rider_with_stray_vendor_row_is_not_listed(self):
        admin = User.objects.create_superuser(email='list-admin@example.com', password='password')
        vendor_user = User.objects.create_user(email='list-vendor@example.com', password='password', role='vendor')
        rider_user = User.objects.create_user(email='list-rider@example.com', password='password', role='rider')
        real = Vendor.objects.create(user=vendor_user, name='Real Kitchen')
        Vendor.objects.create(user=rider_user)  # stray row left by an older signup
        self.client.force_authenticate(admin)

        response = self.client.get(reverse('admin_product_view-vendor_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([v['id'] for v in response.data['results']], [str(real.id)])
