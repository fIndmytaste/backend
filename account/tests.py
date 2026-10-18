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


def _png(name='photo.png'):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (2, 2), (0, 200, 150)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@patch('account.views.account.upload_to_backblaze', return_value={'downloadUrl': 'https://f.backblazeb2.com/new.png'})
class RiderProfilePhotoLockTests(APITestCase):
    """Riders keep their photo unless an admin grants one change."""

    def setUp(self):
        self.user = User.objects.create_user(email='photo-rider@example.com', password='password', role='rider')
        self.rider = Rider.objects.create(user=self.user)
        self.client.force_authenticate(self.user)

    def _upload(self):
        return self.client.patch(
            reverse('ProfileImageUploadView'), {'profile_image': _png()}, format='multipart',
        )

    def _set_photo(self, url='https://f.backblazeb2.com/original.png'):
        self.user.profile_image_url = url
        self.user.save()

    def test_first_photo_is_allowed(self, _upload):
        self.assertEqual(self._upload().status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_image_url, 'https://f.backblazeb2.com/new.png')

    def test_existing_photo_is_locked_with_a_message_the_app_shows(self, upload):
        self._set_photo()

        response = self._upload()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['message'], Rider.PROFILE_PHOTO_LOCKED_MESSAGE)
        upload.assert_not_called()
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_image_url, 'https://f.backblazeb2.com/original.png')

    def test_admin_grant_allows_one_change_then_locks_again(self, _upload):
        self._set_photo()
        self.rider.profile_photo_change_allowed = True
        self.rider.save()

        self.assertEqual(self._upload().status_code, 200)
        self.rider.refresh_from_db()
        self.assertFalse(self.rider.profile_photo_change_allowed)
        self.assertEqual(self._upload().status_code, 403)

    def test_customers_are_not_restricted(self, _upload):
        customer = User.objects.create_user(
            email='photo-customer@example.com', password='password',
            profile_image_url='https://f.backblazeb2.com/me.png',
        )
        self.client.force_authenticate(customer)
        self.assertEqual(self._upload().status_code, 200)


class RiderDocumentPhotoLockTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='doc-rider@example.com', password='password', role='rider',
            profile_image_url='https://f.backblazeb2.com/original.png',
        )
        self.rider = Rider.objects.create(user=self.user)
        self.url = f'/api/v1/riders/{self.rider.id}/upload_documents/'

    @patch('helpers.backblaze.upload_to_backblaze')
    def test_locked_photo_is_reported_and_not_replaced(self, upload):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            self.url, {'profile_photo': _png(), 'mode_of_transport': 'bike'}, format='multipart',
        )

        upload.assert_not_called()
        self.assertEqual(
            response.data['failed_documents'],
            [{'document_type': 'profile_photo', 'reason': Rider.PROFILE_PHOTO_LOCKED_MESSAGE}],
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_image_url, 'https://f.backblazeb2.com/original.png')

    def test_other_users_cannot_upload_a_riders_documents(self):
        stranger = User.objects.create_user(email='stranger@example.com', password='password')
        self.client.force_authenticate(stranger)

        response = self.client.patch(self.url, {'mode_of_transport': 'bike'}, format='multipart')

        self.assertEqual(response.status_code, 404)


class AdminRiderPhotoLockEndpointTests(APITestCase):
    def setUp(self):
        user = User.objects.create_user(
            email='lock-rider@example.com', password='password', role='rider',
            profile_image_url='https://f.backblazeb2.com/original.png',
        )
        self.rider = Rider.objects.create(user=user)
        self.url = reverse('admin_rider-profile-photo-lock', kwargs={'id': self.rider.id})

    def test_admin_grants_and_revokes(self):
        admin = User.objects.create_superuser(email='lock-admin@example.com', password='password')
        self.client.force_authenticate(admin)

        self.assertFalse(self.client.get(self.url).data['data']['can_change_profile_photo'])
        granted = self.client.post(self.url, {'allowed': True}, format='json')
        self.assertTrue(granted.data['data']['can_change_profile_photo'])
        revoked = self.client.post(self.url, {'allowed': False}, format='json')
        self.assertFalse(revoked.data['data']['profile_photo_change_allowed'])

    def test_staff_need_the_riders_page(self):
        from account.models import StaffPagePermission
        staff = User.objects.create_user(email='lock-staff@example.com', password='password', is_staff=True)
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.post(self.url, {'allowed': True}, format='json').status_code, 403)

        StaffPagePermission.objects.create(user=staff, page='riders')
        self.assertEqual(self.client.post(self.url, {'allowed': True}, format='json').status_code, 200)


class RiderGuarantorOwnershipTests(APITestCase):
    def test_other_users_cannot_replace_a_riders_guarantors(self):
        rider = Rider.objects.create(user=User.objects.create_user(
            email='g-rider@example.com', password='password', role='rider',
        ))
        self.client.force_authenticate(User.objects.create_user(email='g-stranger@example.com', password='password'))

        response = self.client.patch(
            f'/api/v1/riders/{rider.id}/guarantors/',
            {'guarantors': [{'name': 'X', 'phone_number': '080', 'relationship': 'friend'}]},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
