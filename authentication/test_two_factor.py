from io import StringIO

import pyotp
from django.conf import settings
from django.core import signing
from django.core.management import call_command
from django.test import override_settings
from rest_framework import status

from audit.models import AuditEvent
from authentication import two_factor
from authentication.models import TwoFactor, User
from authentication.permissions import Role
from authentication.test_admin_lockout import AdminClient
from helpers.testing import TEST_HOSPITAL_DOMAIN, TEST_PASSWORD, TenantAPITestCase, make_user

LOGIN = '/api/v1/auth/login/'
VERIFY = '/api/v1/auth/login/verify/'


def require_two_factor(test):
    '''Class-level override_settings is skipped by the tenant test case, so apply it per test.'''
    override = override_settings(TWO_FACTOR_REQUIRED=True)
    override.enable()
    test.addCleanup(override.disable)


class TwoFactorTestCase(TenantAPITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR)

    def enable(self, user):
        '''Set it up through the API, as the person would; returns (totp, recovery codes).'''
        self.client.force_authenticate(user)
        setup = self.client.post('/api/v1/auth/two-factor/setup/').data
        totp = pyotp.TOTP(setup['secret'])
        confirmed = self.client.post('/api/v1/auth/two-factor/confirm/', {'code': totp.now()}).data
        self.client.force_authenticate(None)
        TwoFactor.objects.filter(user=user).update(last_used_step=None)  # let tests reuse the current code
        return totp, confirmed['recovery_codes']

    def password_step(self, user=None, password=TEST_PASSWORD, **headers):
        return self.client.post(LOGIN, {'email': (user or self.doctor).email, 'password': password}, **headers)

    def code_step(self, challenge, code, **headers):
        return self.client.post(VERIFY, {'challenge': challenge, 'code': code}, **headers)


class SetupTests(TwoFactorTestCase):
    def test_setup_needs_a_matching_code_and_gives_recovery_codes(self):
        self.client.force_authenticate(self.doctor)
        setup = self.client.post('/api/v1/auth/two-factor/setup/').data
        self.assertTrue(setup['qr_code'].startswith('data:image/svg+xml'))
        self.assertIn('otpauth://totp/', setup['otpauth_uri'])
        self.assertEqual(self.client.post('/api/v1/auth/two-factor/confirm/', {'code': '000000'}).status_code, 400)
        self.assertFalse(two_factor.is_enabled(self.doctor))

        confirmed = self.client.post('/api/v1/auth/two-factor/confirm/', {'code': pyotp.TOTP(setup['secret']).now()})
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        self.assertEqual(len(confirmed.data['recovery_codes']), 10)
        self.assertTrue(self.client.get('/api/v1/auth/me/').data['two_factor']['enabled'])
        stored = TwoFactor.objects.get(user=self.doctor).recovery_codes
        self.assertNotIn(confirmed.data['recovery_codes'][0], str(stored))  # stored hashed

    def test_cannot_start_again_while_on(self):
        self.enable(self.doctor)
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.post('/api/v1/auth/two-factor/setup/').status_code, 400)


class SignInTests(TwoFactorTestCase):
    def test_password_then_code(self):
        totp, _ = self.enable(self.doctor)
        first = self.password_step()
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertTrue(first.data['two_factor_required'])
        self.assertNotIn('access', first.data)  # no session yet

        second = self.code_step(first.data['challenge'], totp.now(), HTTP_X_HMS_AUTH_MODE='cookie')
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertIn('access', second.data)
        self.assertIn(settings.AUTH_REFRESH_COOKIE, second.cookies)
        self.assertTrue(AuditEvent.objects.filter(action='login', actor_id=self.doctor.pk).exists())

    def test_without_two_factor_sign_in_is_unchanged(self):
        response = self.password_step()
        self.assertIn('access', response.data)

    def test_a_code_works_once(self):
        totp, _ = self.enable(self.doctor)
        code = totp.now()
        self.assertEqual(self.code_step(self.password_step().data['challenge'], code).status_code, 200)
        self.assertEqual(self.code_step(self.password_step().data['challenge'], code).status_code, 401)

    def test_recovery_codes_work_once(self):
        _, codes = self.enable(self.doctor)
        self.assertEqual(self.code_step(self.password_step().data['challenge'], codes[0].upper()).status_code, 200)
        self.assertEqual(self.code_step(self.password_step().data['challenge'], codes[0]).status_code, 401)
        self.assertEqual(two_factor.status(self.doctor)['recovery_codes_left'], 9)

    def test_wrong_codes_lock_the_account_even_if_the_password_is_entered_again(self):
        self.enable(self.doctor)
        for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS - 1):
            self.code_step(self.password_step().data['challenge'], '000000')
        self.code_step(self.password_step().data['challenge'], '000000')  # a fresh password doesn't reset the count
        self.doctor.refresh_from_db()
        self.assertIsNotNone(self.doctor.locked_until)
        self.assertEqual(self.password_step().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_forged_or_foreign_challenges_are_refused(self):
        totp, _ = self.enable(self.doctor)
        self.assertEqual(self.code_step('not-a-challenge', totp.now()).status_code, 401)
        elsewhere = signing.dumps(
            {'user': self.doctor.pk, 'tenant': 'another_hospital'}, salt=two_factor.CHALLENGE_SALT
        )
        self.assertEqual(self.code_step(elsewhere, totp.now()).status_code, 401)


class RequiredTests(TwoFactorTestCase):
    def setUp(self):
        super().setUp()
        require_two_factor(self)
        self.admin = make_user(Role.ADMIN)

    def test_admins_must_set_it_up_before_anything_else(self):
        # A real sign-in: force_authenticate would skip the authentication class that enforces this
        access = self.password_step(self.admin).data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        blocked = self.client.get('/api/v1/visits/')
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(blocked.data['detail'].code, 'two_factor_setup_required')
        me = self.client.get('/api/v1/auth/me/').data
        self.assertEqual(me['two_factor'], {'enabled': False, 'required': True, 'recovery_codes_left': 0})

    def test_other_staff_are_not_forced(self):
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get('/api/v1/visits/').status_code, status.HTTP_200_OK)

    def test_required_role_cannot_turn_it_off(self):
        totp, _ = self.enable(self.admin)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/v1/visits/').status_code, status.HTTP_200_OK)  # set up: access back
        response = self.client.post('/api/v1/auth/two-factor/disable/', {'password': TEST_PASSWORD, 'code': totp.now()})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ManagementTests(TwoFactorTestCase):
    def test_staff_can_turn_it_off_with_password_and_code(self):
        totp, _ = self.enable(self.doctor)
        self.client.force_authenticate(self.doctor)
        response = self.client.post('/api/v1/auth/two-factor/disable/', {'password': TEST_PASSWORD, 'code': totp.now()})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(two_factor.is_enabled(self.doctor))

    def test_admin_resets_a_colleague_but_not_themselves(self):
        self.enable(self.doctor)
        admin = make_user(Role.ADMIN)
        self.client.force_authenticate(admin)
        response = self.client.post(f'/api/v1/staff/{self.doctor.pk}/reset-two-factor/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(two_factor.is_enabled(self.doctor))
        self.assertEqual(self.client.post(f'/api/v1/staff/{admin.pk}/reset-two-factor/').status_code, 403)

    def test_new_recovery_codes_replace_the_old(self):
        totp, old = self.enable(self.doctor)
        self.client.force_authenticate(self.doctor)
        new = self.client.post('/api/v1/auth/two-factor/recovery-codes/', {'code': totp.now()}).data['recovery_codes']
        self.client.force_authenticate(None)
        self.assertEqual(self.code_step(self.password_step().data['challenge'], old[0]).status_code, 401)
        self.assertEqual(self.code_step(self.password_step().data['challenge'], new[0]).status_code, 200)

    def test_platform_command_resets(self):
        self.enable(self.doctor)
        call_command('reset_two_factor', email=self.doctor.email, schema=self.tenant.schema_name, stdout=StringIO())
        self.assertFalse(two_factor.is_enabled(self.doctor))


class AdminSiteTests(TwoFactorTestCase):
    def setUp(self):
        super().setUp()
        User.objects.filter(pk=self.doctor.pk).update(is_staff=True)
        self.browser = AdminClient(HTTP_HOST=TEST_HOSPITAL_DOMAIN)

    def sign_in(self, code=''):
        return self.browser.post(
            f'/{settings.ADMIN_URL}login/', {'username': self.doctor.email, 'password': TEST_PASSWORD, 'code': code}
        )

    def test_the_admin_sign_in_asks_for_the_code_too(self):
        totp, _ = self.enable(self.doctor)
        self.assertEqual(self.sign_in().status_code, 200)  # no code: refused
        self.assertEqual(self.sign_in('000000').status_code, 200)
        self.assertEqual(self.sign_in(totp.now()).status_code, 302)

    def test_admin_sign_in_refused_until_set_up_when_required(self):
        require_two_factor(self)
        User.objects.filter(pk=self.doctor.pk).update(user_type=Role.ADMIN)
        response = self.sign_in()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Set up two-factor sign-in in the web app first')
