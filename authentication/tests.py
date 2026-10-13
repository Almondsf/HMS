import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from helpers.testing import TEST_PASSWORD, make_user


class LoginTests(APITestCase):
    def setUp(self):
        self.user = make_user(User.UserType.DOCTOR)

    def login(self, password=TEST_PASSWORD):
        return self.client.post('/api/auth/login/', {'email': self.user.email, 'password': password})

    def test_login_returns_tokens_and_user(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['user_type'], 'doctor')

    def test_account_locks_after_repeated_failures(self):
        for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
            self.assertEqual(self.login('wrong-password').status_code, status.HTTP_401_UNAUTHORIZED)

        # Even the correct password is refused while locked
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'].code, 'account_locked')

    def test_successful_login_resets_failure_count(self):
        self.login('wrong-password')
        self.login()
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)


class SessionTests(APITestCase):
    def setUp(self):
        self.user = make_user(User.UserType.RECEPTIONIST)
        tokens = self.client.post(
            '/api/auth/login/', {'email': self.user.email, 'password': TEST_PASSWORD}
        ).data
        self.refresh = tokens['refresh']
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def refresh_works(self):
        return self.client.post('/api/auth/token/refresh/', {'refresh': self.refresh}).status_code == 200

    def test_logout_revokes_refresh_token(self):
        response = self.client.post('/api/auth/logout/', {'refresh': self.refresh})
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertFalse(self.refresh_works())

    def test_cannot_log_out_someone_elses_token(self):
        other = make_user(User.UserType.DOCTOR)
        other_refresh = self.client.post(
            '/api/auth/login/', {'email': other.email, 'password': TEST_PASSWORD}
        ).data['refresh']
        response = self.client.post('/api/auth/logout/', {'refresh': other_refresh})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_change_revokes_sessions(self):
        response = self.client.post('/api/auth/password/change/', {
            'old_password': TEST_PASSWORD, 'new_password': 'An0ther-Str0ng-pass!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.refresh_works())

    def test_me_cannot_change_role(self):
        response = self.client.patch('/api/auth/me/', {'user_type': 'admin', 'first_name': 'Ada'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.user_type, User.UserType.RECEPTIONIST)
        self.assertEqual(self.user.first_name, 'Ada')


class HealthCheckTests(APITestCase):
    def test_health_is_public(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['database'], 'up')


class ProductionSettingsTests(SimpleTestCase):
    '''Production must refuse to boot with insecure configuration.'''

    def check_prod(self, **env):
        env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'hms.settings.prod', **env}
        return subprocess.run(
            [sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
            env=env, capture_output=True, text=True, cwd=settings.BASE_DIR,
        )

    def test_refuses_missing_secret_key(self):
        result = self.check_prod(SECRET_KEY='', ALLOWED_HOSTS='hms.example.com')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY', result.stderr)

    def test_refuses_wildcard_hosts(self):
        result = self.check_prod(SECRET_KEY='x' * 60, ALLOWED_HOSTS='*')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ALLOWED_HOSTS', result.stderr)

    def test_valid_config_passes_deploy_checks(self):
        result = self.check_prod(
            SECRET_KEY='k8$Jq2!vX9#pL4@wZ7&nR1^cT6*mB3%hF0(yD5)gS8_eA2+uK7-iO4=oP9~lQ1', ALLOWED_HOSTS='hms.example.com'
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
