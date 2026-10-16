from django.conf import settings
from django.db import connection
from django.test import Client

from audit.models import AuditEvent
from authentication.models import User
from authentication.permissions import Role
from helpers.testing import TEST_HOSPITAL_DOMAIN, TEST_PASSWORD, TenantAPITestCase, make_user


class AdminClient(Client):
    '''The Django admin at the test hospital's address (restoring the schema, like the API client).'''

    def request(self, **kwargs):
        previous = connection.tenant
        try:
            return super().request(**kwargs)
        finally:
            connection.set_tenant(previous)


class AdminSignInLockoutTests(TenantAPITestCase):
    def setUp(self):
        self.admin = make_user(Role.ADMIN)
        User.objects.filter(pk=self.admin.pk).update(is_staff=True)
        self.browser = AdminClient(HTTP_HOST=TEST_HOSPITAL_DOMAIN)
        self.login_url = f'/{settings.ADMIN_URL}login/'

    def sign_in(self, password):
        return self.browser.post(self.login_url, {'username': self.admin.email, 'password': password})

    def test_admin_sign_in_counts_failures_and_locks(self):
        for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
            self.assertEqual(self.sign_in('wrong-password').status_code, 200)  # form shown again
        self.admin.refresh_from_db()
        self.assertIsNotNone(self.admin.locked_until)
        self.assertEqual(self.sign_in(TEST_PASSWORD).status_code, 200)  # locked: refused even when right
        self.assertTrue(AuditEvent.objects.filter(action='login_blocked').exists())

    def test_one_failure_counts_once(self):
        self.sign_in('wrong-password')
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.failed_login_attempts, 1)
        self.assertEqual(AuditEvent.objects.filter(action='login_failed').count(), 1)

    def test_successful_admin_sign_in_is_logged(self):
        self.assertEqual(self.sign_in(TEST_PASSWORD).status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(action='login', actor_id=self.admin.pk).exists())
