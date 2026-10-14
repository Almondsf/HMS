from rest_framework import status

from authentication.models import User
from helpers.testing import TenantAPITestCase, make_user
from profiles.models import ReceptionistProfile


def user_payload(**overrides):
    return {
        'user': {
            'email': 'new.person@example.com',
            'password': 'Str0ng-pass!',
            'first_name': 'New',
            'last_name': 'Person',
            **overrides,
        }
    }


class ProfileRegistrationAccessTests(TenantAPITestCase):
    def test_anonymous_cannot_register_anyone(self):
        response = self.client.post('/api/create-profile/patients/', user_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_privilege_fields_in_payload_are_ignored(self):
        self.client.force_authenticate(make_user(User.UserType.RECEPTIONIST))
        payload = user_payload(is_superuser=True, is_staff=True, is_admin=True, user_type='admin')

        response = self.client.post('/api/create-profile/patients/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='new.person@example.com')
        self.assertEqual(user.user_type, User.UserType.PATIENT)
        self.assertFalse(user.is_superuser or user.is_staff or user.is_admin)

    def test_receptionist_cannot_create_staff(self):
        self.client.force_authenticate(make_user(User.UserType.RECEPTIONIST))
        payload = {**user_payload(), 'specialty': 'Surgery'}
        response = self.client.post('/api/create-profile/doctors/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_creates_receptionist_with_matching_profile(self):
        self.client.force_authenticate(make_user(User.UserType.ADMIN))

        response = self.client.post('/api/create-profile/receptionists/', user_payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = ReceptionistProfile.objects.get(user__email='new.person@example.com')
        self.assertEqual(profile.user.user_type, User.UserType.RECEPTIONIST)

    def test_weak_password_rejected(self):
        self.client.force_authenticate(make_user(User.UserType.ADMIN))
        response = self.client.post('/api/create-profile/patients/', user_payload(password='12345'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email='new.person@example.com').exists())
