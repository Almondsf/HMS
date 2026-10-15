import tempfile
from io import StringIO
from pathlib import Path

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django_tenants.utils import schema_context


def run(**options):
    out = StringIO()
    try:
        call_command('launch_check', stdout=out, **options)
    except SystemExit as exc:
        return out.getvalue(), exc.code
    return out.getvalue(), 0


class LaunchCheckTests(TestCase):
    def setUp(self):
        with schema_context('public'):
            call_command('setup_platform', 'hms.example', stdout=StringIO())
        self.dist = tempfile.TemporaryDirectory()
        self.addCleanup(self.dist.cleanup)
        Path(self.dist.name, 'index.html').write_text('<html></html>')

    def test_a_development_setup_is_not_ready(self):
        output, code = run()
        self.assertEqual(code, 1)
        self.assertIn('✗ Hospital domain', output)
        self.assertIn('blocking', output)

    def test_a_configured_deployment_passes_with_reminders(self):
        configured = override_settings(
            DEBUG=False,
            TENANT_BASE_DOMAIN='hms.example',
            PLATFORM_DOMAINS=['hms.example'],
            FRONTEND_DIST=Path(self.dist.name),
            FALLBACK_EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
            PROVIDER_ENCRYPTION_KEY='0' * 43 + '=',
            EMAIL_HOST='smtp.example.com',
            DEFAULT_FROM_EMAIL='HMS <no-reply@hms.example>',
            SMS_BACKEND='termii',
            SMS_API_KEY='key',
            SMS_SENDER_ID='HMS',
            SENTRY_DSN='https://key@sentry.example/1',
            SENTRY_FRONTEND_DSN='https://key@sentry.example/2',
        )
        with configured:
            output, code = run()
        self.assertEqual(code, 0, output)
        self.assertIn('✓ Email', output)
        self.assertIn('! Prices', output)  # placeholders still in place
        self.assertIn('! Terms of service', output)  # draft text
        self.assertIn('! Paystack', output)  # not set up

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sends_a_test_email(self):
        output, _ = run(email='me@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('✓ Test email', output)

    @override_settings(SMS_BACKEND='console')
    def test_rejects_an_invalid_test_number(self):
        output, _ = run(sms='12')
        self.assertIn('✗ Test SMS', output)
