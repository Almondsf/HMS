import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status

from authentication.models import User
from authentication.permissions import Role
from helpers.testing import TEST_PASSWORD, SchemaRestoringAPIClient, TenantAPITestCase, make_user
from tenants.models import Hospital

from . import services
from .models import PlanPrice, Subscription, SubscriptionPayment

SECRET = 'sk_test_secret'
WEBHOOK = '/api/v1/platform/billing/paystack/webhook/'


def subscription_for(hospital, **fields):
    subscription = services.start_trial(hospital)
    for name, value in fields.items():
        setattr(subscription, name, value)
    subscription.save()
    return subscription


def paid(hospital, *, plan='pro', interval='monthly', amount=6_000_000, reference='ref-1', **extra):
    '''What Paystack reports for a successful payment (amount in kobo).'''
    return {
        'status': 'success', 'reference': reference, 'amount': amount, 'currency': 'NGN',
        'paid_at': '2026-10-14T09:00:00Z', 'customer': {'customer_code': 'CUS_1'},
        'metadata': {'hospital_id': hospital.pk, 'plan': plan, 'interval': interval}, **extra,
    }  # fmt: skip


class AccessRulesTests(TenantAPITestCase):
    def test_access_follows_the_paid_period_then_grace(self):
        now = timezone.now()
        subscription = subscription_for(self.tenant, current_period_end=now)
        self.assertEqual(subscription.access(now), Subscription.Access.FULL)
        self.assertEqual(subscription.access(now + timedelta(days=3)), Subscription.Access.WARNING)
        self.assertEqual(subscription.access(now + timedelta(days=8)), Subscription.Access.READ_ONLY)

    def test_cancelled_gets_no_grace(self):
        now = timezone.now()
        subscription = subscription_for(self.tenant, current_period_end=now, status=Subscription.Status.CANCELLED)
        self.assertEqual(subscription.access(now + timedelta(days=1)), Subscription.Access.READ_ONLY)

    def test_describe_reports_an_overdue_renewal_as_past_due(self):
        subscription = subscription_for(
            self.tenant, status=Subscription.Status.ACTIVE, current_period_end=timezone.now() - timedelta(days=1)
        )
        summary = services.describe(subscription)
        self.assertEqual(summary['status'], 'past_due')
        self.assertEqual(summary['access'], 'warning')
        self.assertEqual(summary['days_left'], 0)

    def test_month_arithmetic_clamps_to_month_end(self):
        start = timezone.now().replace(year=2026, month=1, day=31)
        self.assertEqual(services.add_months(start, 1).date().isoformat(), '2026-02-28')
        self.assertEqual(services.period_after(start, 'yearly').date().isoformat(), '2027-01-31')


class ReadOnlyMiddlewareTests(TenantAPITestCase):
    def setUp(self):
        self.admin = make_user(Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def lapse(self):
        subscription_for(self.tenant, current_period_end=timezone.now() - timedelta(days=30))

    def test_lapsed_hospital_can_read_but_not_write(self):
        self.lapse()
        self.assertEqual(self.client.get('/api/v1/visits/').status_code, status.HTTP_200_OK)
        response = self.client.patch('/api/v1/hospital/', {'phone': '0800'})
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.json()['code'], 'subscription_lapsed')

    def test_lapsed_hospital_can_still_sign_in_and_pay(self):
        self.lapse()
        self.client.force_authenticate(None)
        login = self.client.post('/api/v1/auth/login/', {'email': self.admin.email, 'password': TEST_PASSWORD})
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.admin)
        with (
            override_settings(PAYSTACK_SECRET_KEY=SECRET),
            patch('subscriptions.paystack.verify_transaction') as verify,
        ):
            verify.return_value = paid(self.tenant)
            response = self.client.post('/api/v1/subscription/confirm/', {'reference': 'ref-1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.client.patch('/api/v1/hospital/', {'phone': '0800'}).status_code, status.HTTP_200_OK)

    def test_grace_period_still_allows_changes(self):
        subscription_for(self.tenant, current_period_end=timezone.now() - timedelta(days=2))
        self.assertEqual(self.client.patch('/api/v1/hospital/', {'phone': '0800'}).status_code, status.HTTP_200_OK)


class PaymentTests(TenantAPITestCase):
    def setUp(self):
        self.subscription = subscription_for(self.tenant)

    def test_payment_extends_from_the_end_of_the_current_period(self):
        period_end = self.subscription.current_period_end
        services.apply_payment(
            hospital=self.tenant, reference='a', source='manual', plan='basic', interval='monthly', amount=25000
        )
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.subscription.current_period_end, services.add_months(period_end, 1))
        self.assertEqual(Hospital.objects.get(pk=self.tenant.pk).plan, 'basic')

    def test_late_payment_starts_from_today(self):
        self.subscription.current_period_end = timezone.now() - timedelta(days=60)
        self.subscription.save()
        services.apply_payment(
            hospital=self.tenant, reference='a', source='manual', plan='pro', interval='yearly', amount=600000
        )
        self.subscription.refresh_from_db()
        self.assertGreater(self.subscription.current_period_end, timezone.now() + timedelta(days=360))

    def test_each_reference_counts_once(self):
        for _ in range(3):
            services.apply_payment(
                hospital=self.tenant, reference='same', source='paystack', plan='pro', interval='monthly', amount=1
            )
        self.assertEqual(SubscriptionPayment.objects.filter(reference='same').count(), 1)
        self.subscription.refresh_from_db()
        self.assertLess(self.subscription.current_period_end, timezone.now() + timedelta(days=50))

    def test_manual_payment_rejects_a_reused_reference(self):
        admin = make_user(Role.ADMIN)
        services.record_manual_payment(
            hospital=self.tenant, plan='pro', interval='monthly', amount=60000, reference='TRF-1', note='', by=admin
        )
        with self.assertRaises(ValidationError):
            services.record_manual_payment(
                hospital=self.tenant, plan='pro', interval='monthly', amount=60000, reference='TRF-1', note='', by=admin
            )


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class CheckoutTests(TenantAPITestCase):
    def setUp(self):
        subscription_for(self.tenant)
        self.client.force_authenticate(make_user(Role.ADMIN))

    def test_only_admins_see_billing(self):
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.client.get('/api/v1/subscription/').status_code, status.HTTP_403_FORBIDDEN)

    def test_summary_lists_prices_and_status(self):
        data = self.client.get('/api/v1/subscription/').data
        self.assertEqual(data['status'], 'trialing')
        self.assertTrue(data['online_payments'])
        self.assertEqual(len(data['prices']), 6)

    @patch('subscriptions.paystack.initialize_transaction')
    def test_checkout_charges_the_listed_price(self, initialize):
        initialize.return_value = {'authorization_url': 'https://checkout.paystack.com/x'}
        response = self.client.post('/api/v1/subscription/checkout/', {'plan': 'pro', 'interval': 'monthly'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['authorization_url'], 'https://checkout.paystack.com/x')
        sent = initialize.call_args.kwargs
        self.assertEqual(sent['amount_kobo'], 6_000_000)
        self.assertEqual(sent['metadata']['hospital_id'], self.tenant.pk)
        self.assertTrue(sent['callback_url'].endswith('/subscription'))

    @patch('subscriptions.paystack.verify_transaction')
    def test_confirm_applies_a_verified_payment(self, verify):
        verify.return_value = paid(self.tenant)
        response = self.client.post('/api/v1/subscription/confirm/', {'reference': 'ref-1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['plan'], 'pro')
        self.assertEqual(response.data['status'], 'active')
        self.assertEqual(Subscription.objects.get(hospital=self.tenant).paystack_customer_code, 'CUS_1')

    @patch('subscriptions.paystack.verify_transaction')
    def test_confirm_rejects_unsuccessful_foreign_or_short_payments(self, verify):
        cases = {
            'failed': paid(self.tenant, status='failed'),
            'other hospital': paid(self.tenant, metadata={'hospital_id': 999, 'plan': 'pro', 'interval': 'monthly'}),
            'underpaid': paid(self.tenant, amount=100),
            'wrong currency': paid(self.tenant, currency='USD'),
        }  # fmt: skip
        for case, data in cases.items():
            with self.subTest(case):
                verify.return_value = data
                response = self.client.post('/api/v1/subscription/confirm/', {'reference': 'ref-1'})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SubscriptionPayment.objects.exists())

    @patch('subscriptions.paystack.disable_subscription')
    def test_cancel_stops_renewal_but_keeps_access(self, disable):
        Subscription.objects.filter(hospital=self.tenant).update(
            paystack_subscription_code='SUB_1', paystack_email_token='tok'
        )
        data = self.client.post('/api/v1/subscription/cancel/').data
        disable.assert_called_once_with(code='SUB_1', email_token='tok')
        self.assertTrue(data['cancel_at_period_end'])
        self.assertEqual(data['access'], 'full')

    def test_unconfigured_paystack_is_a_clear_error(self):
        with override_settings(PAYSTACK_SECRET_KEY=''):
            response = self.client.post('/api/v1/subscription/checkout/', {'plan': 'pro', 'interval': 'monthly'})
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class WebhookTests(TenantAPITestCase):
    def setUp(self):
        with schema_context('public'):
            call_command('setup_platform', 'platform.localhost', stdout=StringIO())
        connection.set_tenant(self.tenant)
        self.subscription = subscription_for(self.tenant)
        self.platform = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')

    def send(self, event, signature=None):
        body = json.dumps(event).encode()
        signature = signature or hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
        return self.platform.generic(
            'POST', WEBHOOK, body, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature
        )

    def test_unsigned_events_are_rejected(self):
        response = self.send({'event': 'charge.success', 'data': paid(self.tenant)}, signature='forged')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SubscriptionPayment.objects.exists())

    def test_renewal_is_applied_once_however_often_it_arrives(self):
        price = PlanPrice.objects.get(plan='pro', interval='monthly')
        price.paystack_plan_code = 'PLN_pro'
        price.save()
        event = {'event': 'charge.success', 'data': paid(self.tenant, metadata={}, plan={'plan_code': 'PLN_pro'})}
        self.subscription.paystack_customer_code = 'CUS_1'
        self.subscription.save()
        first, second = self.send(event), self.send(event)
        self.assertEqual(first.json()['outcome'], 'payment applied')
        self.assertEqual(second.json()['outcome'], 'payment already applied')
        self.assertEqual(SubscriptionPayment.objects.count(), 1)
        self.assertEqual(Hospital.objects.get(pk=self.tenant.pk).plan, 'pro')

    def test_subscription_lifecycle_events(self):
        self.subscription.paystack_customer_code = 'CUS_1'
        self.subscription.save()
        customer = {'customer': {'customer_code': 'CUS_1'}}
        self.send(
            {'event': 'subscription.create', 'data': {**customer, 'subscription_code': 'SUB_1', 'email_token': 't'}}
        )
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.paystack_subscription_code, 'SUB_1')

        self.send({'event': 'invoice.payment_failed', 'data': customer})
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.PAST_DUE)

        self.send({'event': 'subscription.disable', 'data': customer})
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.CANCELLED)

    def test_unknown_customers_and_underpayments_are_acknowledged_not_applied(self):
        unknown = self.send({'event': 'charge.success', 'data': {'customer': {'customer_code': 'CUS_x'}}})
        self.assertEqual(unknown.json()['outcome'], 'ignored: unknown customer')
        short = self.send({'event': 'charge.success', 'data': paid(self.tenant, amount=1)})
        self.assertEqual(short.status_code, status.HTTP_200_OK)
        self.assertTrue(short.json()['outcome'].startswith('rejected'))
        self.assertFalse(SubscriptionPayment.objects.exists())


class PlatformTests(TenantAPITestCase):
    def setUp(self):
        with schema_context('public'):
            call_command('setup_platform', 'platform.localhost', stdout=StringIO())
            self.operator = User.objects.create_user(
                email='ops@example.com', password=TEST_PASSWORD, first_name='Ops', last_name='Team',
                user_type=Role.ADMIN, is_superuser=True,
            )  # fmt: skip
        connection.set_tenant(self.tenant)
        subscription_for(self.tenant)
        self.platform = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')
        self.platform.force_authenticate(self.operator)

    def test_operator_records_a_bank_transfer(self):
        response = self.platform.post(
            f'/api/v1/platform/hospitals/{self.tenant.pk}/record-payment/',
            {'plan': 'basic', 'interval': 'yearly', 'amount': '250000', 'reference': 'TRF-9', 'note': 'GTBank'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        payment = SubscriptionPayment.objects.get()
        self.assertEqual(
            (payment.reference, payment.source, payment.amount), ('manual-TRF-9', 'manual', Decimal(250000))
        )
        self.assertEqual(payment.recorded_by, 'ops@example.com')

    def test_new_hospitals_start_on_a_trial(self):
        response = self.platform.post('/api/v1/platform/hospitals/', {
            'name': 'Mercy Clinic', 'schema_name': 'mercy', 'plan': 'basic',
            'admin_email': 'admin@mercy.example', 'admin_first_name': 'Mary', 'admin_last_name': 'Admin',
        })  # fmt: skip
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        subscription = Subscription.objects.get(hospital__schema_name='mercy')
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertEqual(subscription.days_left(), 13)

    @override_settings(PAYSTACK_SECRET_KEY=SECRET)
    @patch('subscriptions.paystack.create_plan', return_value={'plan_code': 'PLN_new'})
    def test_sync_creates_missing_paystack_plans(self, create_plan):
        call_command('sync_paystack_plans', stdout=StringIO())
        self.assertEqual(create_plan.call_count, 6)
        self.assertFalse(PlanPrice.objects.filter(paystack_plan_code='').exists())
        call_command('sync_paystack_plans', stdout=StringIO())
        self.assertEqual(create_plan.call_count, 6)
