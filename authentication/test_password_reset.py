import re

from django.core import mail
from rest_framework import status

from audit.models import AuditEvent
from authentication.models import User
from helpers.testing import TEST_PASSWORD, TenantAPITestCase, make_user

Role = User.UserType


class AdminResetTests(TenantAPITestCase):
    def setUp(self):
        self.admin = make_user(Role.ADMIN)
        self.nurse = make_user(Role.NURSE)

    def login(self, password):
        return self.client.post('/api/v1/auth/login/', {'email': self.nurse.email, 'password': password})

    def test_temporary_password_must_be_changed(self):
        old_refresh = self.login(TEST_PASSWORD).data['refresh']

        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/v1/staff/{self.nurse.id}/reset-password/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        temporary = response.data['temporary_password']
        self.assertRegex(temporary, r'^[\w]{4}-[\w]{4}-[\w]{4}$')
        self.client.force_authenticate(None)

        # Old sessions are revoked; the old password no longer works
        self.assertEqual(
            self.client.post('/api/v1/auth/token/refresh/', {'refresh': old_refresh}).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(self.login(TEST_PASSWORD).status_code, status.HTTP_401_UNAUTHORIZED)

        login = self.login(temporary)
        self.assertTrue(login.data['user']['must_change_password'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        changed = self.client.post(
            '/api/v1/auth/password/change/', {'old_password': temporary, 'new_password': 'Brand-New-Pass-42'}
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.nurse.refresh_from_db()
        self.assertFalse(self.nurse.must_change_password)
        self.assertTrue(AuditEvent.objects.filter(action='password_reset_by_admin').exists())

    def test_only_admins_reset_and_never_their_own(self):
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.client.post(f'/api/v1/staff/{self.nurse.id}/reset-password/').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'/api/v1/staff/{self.admin.id}/reset-password/').status_code, 400)

    def test_reset_unlocks_a_locked_account(self):
        for _ in range(5):
            self.login('wrong-password')
        self.client.force_authenticate(self.admin)
        temporary = self.client.post(f'/api/v1/staff/{self.nurse.id}/reset-password/').data['temporary_password']
        self.client.force_authenticate(None)
        self.assertEqual(self.login(temporary).status_code, status.HTTP_200_OK)


class EmailResetTests(TenantAPITestCase):
    def setUp(self):
        self.user = make_user(Role.CASHIER)

    def forgot(self, email):
        return self.client.post('/api/v1/auth/password/forgot/', {'email': email})

    def link_parts(self):
        [message] = mail.outbox
        match = re.search(r'(https?://\S+)/reset-password\?uid=(\S+)&token=(\S+)', message.body)
        return match.group(1), match.group(2), match.group(3)

    def reset(self, uid, token, password='Brand-New-Pass-42'):
        return self.client.post('/api/v1/auth/password/reset/', {'uid': uid, 'token': token, 'new_password': password})

    def test_same_answer_whether_or_not_the_account_exists(self):
        unknown = self.forgot('nobody@example.com')
        known = self.forgot(self.user.email)
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown.data, known.data)
        self.assertEqual(len(mail.outbox), 1)  # only the real account got an email

    def test_reset_by_email_link(self):
        self.forgot(self.user.email)
        base, uid, token = self.link_parts()
        self.assertEqual(base, 'http://test-hospital.localhost:5173')  # FRONTEND_URL in development

        self.assertEqual(self.reset(uid, token).status_code, status.HTTP_200_OK)
        login = self.client.post('/api/v1/auth/login/', {'email': self.user.email, 'password': 'Brand-New-Pass-42'})
        self.assertEqual(login.status_code, status.HTTP_200_OK)

        # Links are single-use
        self.assertEqual(self.reset(uid, token, 'Another-Pass-77').status_code, status.HTTP_400_BAD_REQUEST)

    def test_bad_links_and_weak_passwords_are_refused(self):
        self.forgot(self.user.email)
        _, uid, token = self.link_parts()
        self.assertEqual(self.reset(uid, token[:-2] + 'xx').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.reset('bm9wZQ', token).status_code, status.HTTP_400_BAD_REQUEST)
        weak = self.reset(uid, token, '12345')
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', weak.data)

    def test_patients_without_passwords_get_no_email(self):
        patient = make_user(Role.PATIENT)
        patient.set_unusable_password()
        patient.save()
        self.forgot(patient.email)
        self.assertEqual(len(mail.outbox), 0)
