import re
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status

from helpers.testing import SchemaRestoringAPIClient
from subscriptions.models import Subscription
from tenants.models import Hospital

from . import services
from .models import Signup

PASSWORD = 'Sunr1se-clinic-pass'


def details(**overrides):
    return {
        'hospital_name': 'Sunrise Clinic', 'address': 'sunrise', 'plan': 'pro', 'first_name': 'Sade',
        'last_name': 'Bello', 'email': 'sade@sunrise.example', 'phone': '+2348012345678', 'password': PASSWORD,
        'accept_terms': True, **overrides,
    }  # fmt: skip


class SignupTestCase(TestCase):
    def setUp(self):
        cache.clear()
        with schema_context('public'):
            call_command('setup_platform', 'platform.localhost', stdout=StringIO())
        self.client = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')

    def sign_up(self, **overrides):
        return self.client.post('/api/v1/signup/', details(**overrides))

    def emailed_token(self):
        return re.search(r'token=([\w-]+)', mail.outbox[-1].body).group(1)


class SignupRequestTests(SignupTestCase):
    def test_signup_only_sends_a_verification_link(self):
        response = self.sign_up()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/signup/verify?token=', mail.outbox[0].body)
        signup = Signup.objects.get()
        self.assertEqual(signup.status, Signup.Status.PENDING)
        self.assertNotEqual(signup.password_hash, PASSWORD)
        self.assertFalse(Hospital.objects.filter(schema_name='sunrise').exists())

    def test_bad_addresses_are_explained(self):
        for address, reason in [('www', 'reserved'), ('1clinic', 'letters'), ('a--b', 'letters'), ('ab', 'letters')]:
            with self.subTest(address):
                response = self.client.get('/api/v1/signup/availability/', {'address': address})
                self.assertFalse(response.data['available'])
                self.assertIn(reason, response.data['reason'])
                self.assertEqual(self.sign_up(address=address).status_code, status.HTTP_400_BAD_REQUEST)

    def test_free_address_shows_its_url(self):
        response = self.client.get('/api/v1/signup/availability/', {'address': 'Sunrise-Clinic'})
        self.assertTrue(response.data['available'])
        self.assertIn('sunrise-clinic.', response.data['url'])

    def test_terms_must_be_accepted_and_versions_are_recorded(self):
        refused = self.sign_up(accept_terms=False)
        self.assertEqual(refused.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('accept_terms', refused.data)
        self.sign_up()
        signup = Signup.objects.get()
        self.assertEqual((signup.terms_version, signup.privacy_version), ('draft-1', 'draft-1'))
        self.assertIsNotNone(signup.terms_accepted_at)

    def test_weak_password_is_refused(self):
        response = self.sign_up(password='password')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_bots_filling_the_hidden_field_get_nothing(self):
        self.assertEqual(self.sign_up(website='http://spam.example').status_code, status.HTTP_201_CREATED)
        self.assertFalse(Signup.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_repeat_signups_for_one_email_are_capped(self):
        for n in range(services.SIGNUPS_PER_EMAIL_PER_DAY + 2):
            self.assertEqual(self.sign_up(address=f'clinic-{n}').status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), services.SIGNUPS_PER_EMAIL_PER_DAY)

    def test_plans_are_public(self):
        data = self.client.get('/api/v1/signup/plans/').data
        self.assertEqual(data['trial_days'], 14)
        self.assertEqual(len(data['prices']), 6)

    def test_email_failure_is_reported_and_leaves_nothing(self):
        with patch('signup.services.send_mail', side_effect=OSError('smtp down')):
            response = self.sign_up()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(Signup.objects.exists())


class VerificationTests(SignupTestCase):
    def verify(self, token):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/v1/signup/verify/', {'token': token})

    def test_verified_signup_becomes_a_working_hospital(self):
        self.sign_up()
        token = self.emailed_token()

        response = self.verify(token)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'provisioning')  # the setup runs after the response
        progress = self.client.post('/api/v1/signup/status/', {'token': token}).data
        self.assertEqual(progress['status'], 'ready', progress)
        self.assertTrue(progress['login_url'].endswith('/login'))
        self.assertIn('sunrise.', progress['login_url'])

        hospital = Hospital.objects.get(schema_name='sunrise')
        self.assertEqual((hospital.name, hospital.plan, hospital.phone), ('Sunrise Clinic', 'pro', '+2348012345678'))
        self.assertEqual(Subscription.objects.get(hospital=hospital).status, Subscription.Status.TRIALING)
        self.assertEqual(Signup.objects.get().password_hash, '')
        self.assertIn('is ready', mail.outbox[-1].subject)

        # The owner signs in with the password they chose
        login = SchemaRestoringAPIClient(HTTP_HOST='sunrise.localhost').post(
            '/api/v1/auth/login/', {'email': 'sade@sunrise.example', 'password': PASSWORD}
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK, login.data)

        # The link is harmless to click again, and the address is now taken
        again = self.client.post('/api/v1/signup/verify/', {'token': token})
        self.assertEqual(again.data['status'], 'ready')
        self.assertEqual(Hospital.objects.filter(schema_name='sunrise').count(), 1)
        taken = self.client.get('/api/v1/signup/availability/', {'address': 'sunrise'}).data
        self.assertEqual(taken['reason'], 'This address is already taken.')

    def test_unknown_and_expired_links_are_refused(self):
        self.assertEqual(self.verify('not-a-real-token').status_code, status.HTTP_400_BAD_REQUEST)
        self.sign_up()
        Signup.objects.update(created_at=timezone.now() - timedelta(days=3))
        response = self.verify(self.emailed_token())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expired', str(response.data))

    def test_failed_setup_is_reported_kindly(self):
        self.sign_up()
        taken = ValidationError({'schema_name': 'A hospital with this identifier already exists.'})
        with patch('signup.services.provision_hospital', side_effect=taken):
            response = self.verify(self.emailed_token())
        self.assertEqual(response.data['status'], 'provisioning')  # reported before the setup runs
        progress = self.client.post('/api/v1/signup/status/', {'token': self.emailed_token()}).data
        self.assertEqual(progress['status'], 'failed')
        self.assertIn('taken', progress['error'])

    def test_status_needs_a_real_token(self):
        self.assertEqual(self.client.post('/api/v1/signup/status/', {'token': 'nope'}).status_code, 404)


class ProcessSignupsTests(SignupTestCase):
    def test_retries_interrupted_setups_and_purges_unverified(self):
        self.sign_up(address='stuck-one')
        self.sign_up(address='never-verified', email='other@example.com')
        Signup.objects.filter(address='stuck-one').update(
            status=Signup.Status.PROVISIONING, provisioning_started_at=timezone.now() - timedelta(hours=1)
        )
        Signup.objects.filter(address='never-verified').update(created_at=timezone.now() - timedelta(days=8))

        with patch('signup.services.provision', side_effect=lambda pk: Signup.objects.get(pk=pk)) as provision:
            call_command('process_signups', stdout=StringIO())

        provision.assert_called_once_with(Signup.objects.get(address='stuck-one').pk)
        self.assertFalse(Signup.objects.filter(address='never-verified').exists())


class PlatformSiteTests(SignupTestCase):
    def test_platform_serves_the_web_app_or_404s_without_it(self):
        response = self.client.get('/signup')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND))
        self.assertEqual(self.client.get('/api/v1/visits/').status_code, status.HTTP_404_NOT_FOUND)
