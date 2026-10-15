from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase, override_settings
from django_tenants.utils import schema_context
from rest_framework import status

from audit.models import AuditEvent
from authentication.models import User
from authentication.permissions import Role
from helpers import sms
from helpers.testing import TEST_PASSWORD, SchemaRestoringAPIClient

from . import crypto
from .models import ProviderConfig
from .registry import ProviderError

BASE = '/api/v1/platform/providers/'
ZEPTO = {'api_token': 'Zoho-enczapikey secret-token-1234', 'from_email': 'HMS <no-reply@hms.example>'}
PROVIDER_BACKEND = 'providers.email.ProviderEmailBackend'


class ProviderApiTestCase(TestCase):
    def setUp(self):
        with schema_context('public'):
            call_command('setup_platform', 'platform.localhost', stdout=StringIO())
            self.operator = User.objects.create_user(
                email='ops@example.com', password=TEST_PASSWORD, first_name='Ops', last_name='Team',
                user_type=Role.ADMIN, is_superuser=True,
            )  # fmt: skip
        self.client = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')
        self.client.force_authenticate(self.operator)

    def save(self, channel, provider, values):
        return self.client.put(f'{BASE}{channel}/{provider}/', values, format='json')

    def send_test(self, channel, provider, to, reply=None):
        with patch('providers.registry.post_json', return_value=reply or {'message_id': 'x'}) as post:
            response = self.client.post(f'{BASE}{channel}/{provider}/test/', {'to': to}, format='json')
        return response, post

    def switch(self, channel, provider):
        return self.client.put(f'{BASE}{channel}/', {'provider': provider}, format='json')


class ProviderSetupTests(ProviderApiTestCase):
    def test_only_platform_operators(self):
        anonymous = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')
        self.assertEqual(anonymous.get(BASE).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_catalog_and_status(self):
        data = self.client.get(BASE).data
        names = {(item['channel'], item['name']) for item in data['catalog']}
        self.assertTrue({('email', 'zeptomail'), ('email', 'smtp'), ('sms', 'termii')} <= names)
        self.assertEqual(data['channels']['email']['source'], 'server settings')

    def test_secrets_are_encrypted_and_never_returned(self):
        response = self.save('email', 'zeptomail', ZEPTO)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['secrets'], {'api_token': '••••1234'})
        stored = ProviderConfig.objects.get(provider='zeptomail')
        self.assertNotIn('secret-token', stored.encrypted_secrets)
        self.assertEqual(crypto.decrypt(stored.encrypted_secrets)['api_token'], ZEPTO['api_token'])
        self.assertNotIn('secret-token', str(self.client.get(BASE).data))

    def test_blank_secret_keeps_the_stored_one(self):
        self.save('email', 'zeptomail', ZEPTO)
        self.save('email', 'zeptomail', {'api_token': '', 'from_email': 'Ops <ops@hms.example>'})
        stored = ProviderConfig.objects.get(provider='zeptomail')
        self.assertEqual(crypto.decrypt(stored.encrypted_secrets)['api_token'], ZEPTO['api_token'])
        self.assertEqual(stored.settings['from_email'], 'Ops <ops@hms.example>')

    def test_settings_are_validated(self):
        missing = self.save('email', 'zeptomail', {'from_email': 'no-reply@hms.example'})
        self.assertIn('api_token', missing.data)
        bad = self.save('email', 'zeptomail', {**ZEPTO, 'api_host': 'evil.example.com'})
        self.assertIn('api_host', bad.data)
        self.assertIn(
            'port', self.save('email', 'smtp', {'host': 'h', 'port': 'abc', 'username': 'u', 'password': 'p'}).data
        )
        self.assertIn('nonsense', self.save('sms', 'termii', {'api_key': 'k', 'sender_id': 'HMS', 'nonsense': 1}).data)
        self.assertEqual(self.save('sms', 'carrier-pigeon', {}).status_code, status.HTTP_400_BAD_REQUEST)


class SwitchingTests(ProviderApiTestCase):
    def test_switch_to_zeptomail_after_a_successful_test(self):
        self.save('email', 'zeptomail', ZEPTO)
        self.assertEqual(self.switch('email', 'zeptomail').status_code, status.HTTP_400_BAD_REQUEST)  # untested

        response, post = self.send_test('email', 'zeptomail', 'me@example.com')
        self.assertTrue(response.data['last_test_ok'], response.data)
        url, payload, headers = post.call_args.args
        self.assertEqual(url, 'https://api.zeptomail.com/v1.1/email')
        self.assertEqual(headers['Authorization'], 'Zoho-enczapikey secret-token-1234')  # prefix not doubled
        self.assertEqual(payload['from'], {'address': 'no-reply@hms.example', 'name': 'HMS'})
        self.assertEqual(payload['to'], [{'email_address': {'address': 'me@example.com'}}])

        switched = self.switch('email', 'zeptomail')
        self.assertEqual(switched.status_code, status.HTTP_200_OK, switched.data)
        self.assertEqual(switched.data['channels']['email'], {'using': 'ZeptoMail (Zoho)', 'source': 'dashboard'})
        self.assertTrue(AuditEvent.objects.filter(action='providers.activated').exists())

        # Every email in the platform now goes through ZeptoMail
        with override_settings(EMAIL_BACKEND=PROVIDER_BACKEND), patch('providers.registry.post_json') as post:
            mail.send_mail('Hello', 'Body', None, ['someone@example.com'])
        self.assertEqual(post.call_args.args[1]['subject'], 'Hello')

    def test_failed_test_blocks_switching(self):
        self.save('email', 'zeptomail', ZEPTO)
        with patch('providers.registry.post_json', side_effect=ProviderError('Refused (401): invalid token')):
            response = self.client.post(f'{BASE}email/zeptomail/test/', {'to': 'me@example.com'}, format='json')
        self.assertFalse(response.data['last_test_ok'])
        self.assertIn('invalid token', response.data['last_test_error'])
        self.assertEqual(self.switch('email', 'zeptomail').status_code, status.HTTP_400_BAD_REQUEST)

    def test_changing_settings_needs_a_new_test(self):
        self.save('email', 'zeptomail', ZEPTO)
        self.send_test('email', 'zeptomail', 'me@example.com')
        self.save('email', 'zeptomail', {'api_token': 'Zoho-enczapikey another-token-9999'})
        self.assertIsNone(ProviderConfig.objects.get(provider='zeptomail').last_test_ok)
        self.assertEqual(self.switch('email', 'zeptomail').status_code, status.HTTP_400_BAD_REQUEST)

    def test_switching_back_to_server_settings(self):
        self.save('email', 'zeptomail', ZEPTO)
        self.send_test('email', 'zeptomail', 'me@example.com')
        self.switch('email', 'zeptomail')
        data = self.switch('email', None).data
        self.assertEqual(data['channels']['email']['source'], 'server settings')
        self.assertFalse(ProviderConfig.objects.filter(is_active=True).exists())
        with override_settings(
            EMAIL_BACKEND=PROVIDER_BACKEND, FALLBACK_EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            mail.send_mail('Hello', 'Body', None, ['someone@example.com'])
        self.assertEqual(len(mail.outbox), 1)

    def test_console_is_never_the_active_provider_in_production(self):
        self.save('sms', 'console', {})
        self.send_test('sms', 'console', '08031234567')
        self.assertEqual(self.switch('sms', 'console').status_code, status.HTTP_400_BAD_REQUEST)

    def test_termii_from_the_dashboard_sends_all_sms(self):
        self.save(
            'sms', 'termii', {'api_key': 'tk-123456', 'sender_id': 'HMS', 'base_url': 'https://v3.api.termii.com'}
        )
        response, post = self.send_test('sms', 'termii', '0803 123 4567')
        self.assertTrue(response.data['last_test_ok'], response.data)
        self.assertEqual(post.call_args.args[1]['to'], '2348031234567')
        self.switch('sms', 'termii')
        self.assertTrue(sms.available())
        with patch('providers.registry.post_json', return_value={'message_id': 'T1'}) as post:
            self.assertEqual(sms.send(to='+2348031234567', body='Hi'), ('termii', 'T1'))
        url, payload, _ = post.call_args.args
        self.assertEqual(
            (url, payload['from'], payload['api_key']), ('https://v3.api.termii.com/api/sms/send', 'HMS', 'tk-123456')
        )

    def test_invalid_test_number(self):
        self.save('sms', 'termii', {'api_key': 'tk-123456', 'sender_id': 'HMS'})
        response, _ = self.send_test('sms', 'termii', '12')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CryptoTests(TestCase):
    def test_a_changed_key_is_explained(self):
        token = crypto.encrypt({'api_key': 'x'})
        with override_settings(PROVIDER_ENCRYPTION_KEY=crypto.generate_key()):
            with self.assertRaisesMessage(ImproperlyConfigured, 'PROVIDER_ENCRYPTION_KEY has changed'):
                crypto.decrypt(token)

    @override_settings(PROVIDER_ENCRYPTION_KEY='', DEBUG=False)
    def test_production_needs_a_key(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'Set PROVIDER_ENCRYPTION_KEY'):
            crypto.encrypt({'api_key': 'x'})

    def test_masking(self):
        self.assertEqual(crypto.mask('abcdef123'), '••••f123')
        self.assertEqual(crypto.mask(''), '')
