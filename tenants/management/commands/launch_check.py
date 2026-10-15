'''
Is this deployment ready for real hospitals? Run it on the server (Render
Shell) after deploying, and fix what it reports until everything is green.

    python manage.py launch_check
    python manage.py launch_check --email you@example.com --sms +2348030000000

Exits with status 1 when something blocks launch, so it can also gate a deploy.
'''

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django_tenants.utils import get_public_schema_name

OK, WARN, FAIL = 'ok', 'warn', 'fail'
MARKS = {OK: '✓', WARN: '!', FAIL: '✗'}
PLACEHOLDER_PRICES = {('basic', 'monthly'): 25000, ('pro', 'monthly'): 60000, ('enterprise', 'monthly'): 150000}


class Command(BaseCommand):
    help = 'Check that this deployment is ready for real hospitals: settings, email, payments, SMS, legal text.'

    def add_arguments(self, parser):
        parser.add_argument('--email', help='Also send a test email to this address')
        parser.add_argument('--sms', help='Also send a test SMS to this number')

    def handle(self, *args, email, sms, **options):
        self.results = []
        for section in (
            self.site,
            self.database,
            self.mail,
            self.payments,
            self.monitoring,
            self.text_messages,
            self.legal,
        ):
            section()
        if email:
            self.send_test_email(email)
        if sms:
            self.send_test_sms(sms)

        width = max(len(name) for _, name, _ in self.results)
        for status, name, detail in self.results:
            style = {OK: self.style.SUCCESS, WARN: self.style.WARNING, FAIL: self.style.ERROR}[status]
            self.stdout.write(f'{style(MARKS[status])} {name.ljust(width)}  {detail}')
        self.stdout.write(
            '\nNot checked here: DNS for your domain and *.domain, database backups (docs/BACKUP_AND_RESTORE.md), '
            'the Paystack webhook URL, and the hms-reminders cron job in Render.'
        )
        failures = sum(status == FAIL for status, _, _ in self.results)
        warnings = sum(status == WARN for status, _, _ in self.results)
        summary = f'\n{failures} blocking, {warnings} to review, {len(self.results) - failures - warnings} ready.'
        if failures:
            self.stdout.write(self.style.ERROR(summary + ' Fix the ✗ items before taking real hospitals.'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(summary))

    def report(self, status, name, detail):
        self.results.append((status, name, detail))

    # ---- sections ----

    def site(self):
        debug = settings.DEBUG
        self.report(FAIL if debug else OK, 'Debug mode', 'ON: never in production' if debug else 'off')
        base = settings.TENANT_BASE_DOMAIN
        self.report(
            FAIL if base == 'localhost' else OK,
            'Hospital domain',
            f'hospitals at <name>.{base}' if base != 'localhost' else 'set TENANT_BASE_DOMAIN to your domain',
        )
        local = ('localhost', '127.0.0.1')
        platforms = [d for d in settings.PLATFORM_DOMAINS if not d.endswith('.onrender.com') and d not in local]
        self.report(
            OK if platforms else FAIL,
            'Platform domain',
            ', '.join(platforms) if platforms else 'set PLATFORM_DOMAINS to your domain (e.g. yourdomain.com)',
        )
        index = settings.FRONTEND_DIST / 'index.html'
        self.report(
            OK if index.is_file() else FAIL, 'Web app', 'built' if index.is_file() else 'not built (frontend/dist)'
        )
        name = settings.PRODUCT_NAME
        renamed = name != 'HMS'
        self.report(OK if renamed else WARN, 'Product name', name if renamed else '"HMS" (set PRODUCT_NAME)')

    def database(self):
        from tenants.models import Domain, Hospital

        try:
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        except Exception as exc:  # noqa: BLE001 (report any database problem)
            self.report(FAIL, 'Database', f'cannot connect: {exc}')
            return
        self.report(
            FAIL if pending else OK,
            'Migrations',
            f'{len(pending)} not applied: run migrate' if pending else 'up to date',
        )
        public = get_public_schema_name()
        registered = Domain.objects.filter(tenant__schema_name=public).count()
        self.report(OK if registered else FAIL, 'Platform registered', 'yes' if registered else 'run setup_platform')
        hospitals = Hospital.objects.exclude(schema_name=public)
        self.report(OK, 'Hospitals', f'{hospitals.count()} ({hospitals.filter(is_active=True).count()} active)')

    def mail(self):
        from providers import services as providers
        from providers.models import ProviderConfig

        active = ProviderConfig.objects.filter(channel='email', is_active=True).first()
        if active:
            ok = active.last_test_ok and active.provider != 'console'
            self.report(
                OK if ok else WARN,
                'Email',
                f'{active.provider} (chosen in the operator dashboard)'
                + ('' if ok else ': send it a test from the Providers page'),
            )
        else:
            label, _ = providers.status('email')
            backend = settings.FALLBACK_EMAIL_BACKEND.rsplit('.', 2)[-2]
            if backend != 'smtp' or not settings.EMAIL_HOST:
                self.report(FAIL, 'Email', f'{label}: emails are not delivered. Set up ZeptoMail under Providers')
            else:
                self.report(OK, 'Email', f'{label} (server settings)')
        sender = settings.DEFAULT_FROM_EMAIL
        self.report(
            WARN if 'localhost' in sender else OK,
            'Email sender',
            sender if 'localhost' not in sender else f'{sender}: set DEFAULT_FROM_EMAIL to an address on your domain',
        )
        key = settings.PROVIDER_ENCRYPTION_KEY
        self.report(
            OK if key else (WARN if settings.DEBUG else FAIL),
            'Provider key encryption',
            'set' if key else 'set PROVIDER_ENCRYPTION_KEY before saving provider keys in the dashboard',
        )

    def payments(self):
        from subscriptions import paystack
        from subscriptions.models import PlanPrice

        key = settings.PAYSTACK_SECRET_KEY
        if not key:
            self.report(WARN, 'Paystack', 'not set up: hospitals can only pay by bank transfer')
        else:
            mode = 'LIVE' if key.startswith('sk_live_') else 'TEST' if key.startswith('sk_test_') else 'unknown'
            try:
                paystack._request('GET', '/plan?perPage=1')
            except paystack.PaystackError as exc:
                self.report(FAIL, 'Paystack', f'{mode} key rejected: {exc}')
            else:
                self.report(
                    OK if mode == 'LIVE' else WARN,
                    'Paystack',
                    f'{mode} key works' + ('' if mode == 'LIVE' else ': switch to the live key for real payments'),
                )
            unsynced = PlanPrice.objects.filter(is_active=True, paystack_plan_code='').count()
            self.report(
                WARN if unsynced else OK,
                'Paystack plans',
                f'{unsynced} price(s) without a plan: run sync_paystack_plans (needed for auto-renewal)'
                if unsynced
                else 'in sync',
            )
        placeholders = [
            f'{plan} {interval}'
            for (plan, interval), amount in PLACEHOLDER_PRICES.items()
            if PlanPrice.objects.filter(plan=plan, interval=interval, amount=amount).exists()
        ]
        self.report(
            WARN if placeholders else OK,
            'Prices',
            f'still the placeholders ({", ".join(placeholders)}): set yours in the platform admin'
            if placeholders
            else 'set',
        )

    def monitoring(self):
        for name, value in (
            ('Error monitoring (API)', settings.SENTRY_DSN),
            ('Error monitoring (app)', settings.SENTRY_FRONTEND_DSN),
        ):
            self.report(
                OK if value else WARN, name, 'Sentry on' if value else 'off: set the Sentry DSN to hear about errors'
            )

    def text_messages(self):
        from providers import services as providers

        provider = providers.current('sms')
        label, source = providers.status('sms')
        if provider is None:
            self.report(
                WARN, 'SMS', 'off: appointment confirmations and reminders are not sent. Set up Termii under Providers'
            )
        elif not provider.delivers:
            self.report(FAIL, 'SMS', f'{label}: messages are only printed. Set up Termii under Providers')
        else:
            sender = provider.values.get('sender_id')
            self.report(
                OK if sender else WARN, 'SMS',
                f'{label} ({source})' + ('' if sender else ': set a sender ID registered with Termii'),
            )  # fmt: skip

    def legal(self):
        from legal.models import LegalDocument

        for kind, label in LegalDocument.Kind.choices:
            document = LegalDocument.current(kind)
            if document is None:
                self.report(FAIL, label, 'missing: signup needs it')
            elif document.is_draft:
                self.report(WARN, label, f'version {document.version} is a draft: publish a lawyer-approved version')
            else:
                self.report(OK, label, f'version {document.version}')

    # ---- live tests ----

    def send_test_email(self, address):
        try:
            send_mail(f'{settings.PRODUCT_NAME} test email', 'If you can read this, email works.', None, [address])
        except Exception as exc:  # noqa: BLE001 (report any delivery problem)
            self.report(FAIL, 'Test email', f'not sent: {exc}')
        else:
            self.report(OK, 'Test email', f'sent to {address}: check it arrived (and not in spam)')

    def send_test_sms(self, number):
        from helpers import sms

        to = sms.normalize(number)
        if not to:
            self.report(FAIL, 'Test SMS', f'"{number}" is not a valid mobile number')
            return
        try:
            provider, message_id = sms.send(to=to, body=f'{settings.PRODUCT_NAME} test message: SMS works.')
        except sms.SmsError as exc:
            self.report(FAIL, 'Test SMS', f'not sent: {exc}')
        else:
            self.report(OK, 'Test SMS', f'sent to {to} via {provider} ({message_id}): check it arrived')
