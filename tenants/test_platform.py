from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status

from audit.models import AuditEvent
from authentication.models import User
from authentication.permissions import Role
from helpers.testing import TEST_PASSWORD, SchemaRestoringAPIClient, TenantAPITestCase, make_user
from signup.models import Signup
from subscriptions import services as subscriptions
from subscriptions.models import Subscription


class OperatorTestCase(TenantAPITestCase):
    def setUp(self):
        with schema_context('public'):
            call_command('setup_platform', 'platform.localhost', stdout=StringIO())
            self.operator = User.objects.create_user(
                email='ops@example.com', password=TEST_PASSWORD, first_name='Ops', last_name='Team',
                user_type=Role.ADMIN, is_superuser=True,
            )  # fmt: skip
        connection.set_tenant(self.tenant)
        self.subscription = subscriptions.start_trial(self.tenant)
        self.platform = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')
        self.platform.force_authenticate(self.operator)

    def end_trial_in(self, days):
        Subscription.objects.filter(pk=self.subscription.pk).update(
            current_period_end=timezone.now() + timedelta(days=days)
        )


class OverviewTests(OperatorTestCase):
    def test_only_platform_operators_see_it(self):
        anonymous = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')
        self.assertEqual(anonymous.get('/api/v1/platform/overview/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(make_user(Role.ADMIN))  # a hospital admin, at their hospital
        self.assertEqual(self.client.get('/api/v1/platform/overview/').status_code, status.HTTP_404_NOT_FOUND)

    def test_trial_ending_soon_needs_attention(self):
        self.end_trial_in(3)
        data = self.platform.get('/api/v1/platform/overview/').data
        self.assertEqual(data['hospitals']['trialing'], 1)
        self.assertEqual([row['id'] for row in data['attention']['trials_ending']], [self.tenant.pk])

    def test_paying_hospital_counts_towards_revenue(self):
        subscriptions.record_manual_payment(
            hospital=self.tenant,
            plan='pro',
            interval='yearly',
            amount=600000,
            reference='T1',
            note='',
            by=self.operator,
        )
        data = self.platform.get('/api/v1/platform/overview/').data
        self.assertEqual(data['hospitals']['paying'], 1)
        self.assertEqual(float(data['revenue']['this_month']), 600000)
        self.assertEqual(float(data['revenue']['monthly_recurring']), 50000)  # 600,000 a year
        self.assertEqual(float(data['revenue']['by_month'][-1]['total']), 600000)

    def test_overdue_and_lapsed_hospitals_are_listed(self):
        self.end_trial_in(-3)
        self.assertEqual(len(self.platform.get('/api/v1/platform/overview/').data['attention']['overdue']), 1)
        self.end_trial_in(-30)
        data = self.platform.get('/api/v1/platform/overview/').data
        self.assertEqual(data['hospitals']['lapsed'], 1)
        self.assertEqual(len(data['attention']['lapsed']), 1)


class HospitalManagementTests(OperatorTestCase):
    def test_search_and_detail_with_usage(self):
        found = self.platform.get('/api/v1/platform/hospitals/', {'search': 'Test Hosp'}).data['results']
        self.assertEqual([hospital['id'] for hospital in found], [self.tenant.pk])
        self.assertEqual(self.platform.get('/api/v1/platform/hospitals/', {'search': 'nowhere'}).data['count'], 0)

        make_user(Role.DOCTOR)
        detail = self.platform.get(f'/api/v1/platform/hospitals/{self.tenant.pk}/').data
        self.assertEqual(detail['usage']['active_staff'], 1)
        self.assertIn('payments', detail)

    def test_extend_gives_extra_days_and_is_audited(self):
        self.end_trial_in(2)
        response = self.platform.post(
            f'/api/v1/platform/hospitals/{self.tenant.pk}/extend/', {'days': 10, 'reason': 'Onboarding call'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['subscription']['days_left'], 11)
        with schema_context('public'):
            self.assertTrue(AuditEvent.objects.filter(action='subscription.extended').exists())

    def test_extend_is_limited(self):
        for days in (0, 91):
            response = self.platform.post(
                f'/api/v1/platform/hospitals/{self.tenant.pk}/extend/', {'days': days, 'reason': 'x'}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_extending_an_overdue_hospital_clears_past_due(self):
        Subscription.objects.filter(pk=self.subscription.pk).update(
            status=Subscription.Status.PAST_DUE, current_period_end=timezone.now() - timedelta(days=2)
        )
        self.platform.post(
            f'/api/v1/platform/hospitals/{self.tenant.pk}/extend/', {'days': 7, 'reason': 'Transfer pending'}
        )
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.subscription.days_left(), 6)


class SignupManagementTests(OperatorTestCase):
    def make_signup(self, **fields):
        defaults = {
            'hospital_name': 'Sunrise', 'address': 'sunrise', 'plan': 'pro', 'first_name': 'S', 'last_name': 'B',
            'email': 's@example.com', 'password_hash': 'hash', 'token_hash': str(Signup.objects.count()),
            'status': Signup.Status.FAILED,
        }  # fmt: skip
        return Signup.objects.create(**{**defaults, **fields})

    def test_signups_are_listed_without_secrets(self):
        self.make_signup()
        rows = self.platform.get('/api/v1/platform/signups/', {'status': 'failed'}).data['results']
        self.assertEqual(len(rows), 1)
        self.assertNotIn('password_hash', rows[0])
        self.assertNotIn('token_hash', rows[0])

    @patch('signup.services.start_provisioning')
    def test_failed_signup_can_be_retried(self, start):
        signup = self.make_signup()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.platform.post(f'/api/v1/platform/signups/{signup.pk}/retry/')
        self.assertEqual(response.data['status'], 'provisioning')
        start.assert_called_once_with(signup.pk)

    def test_only_failed_signups_with_a_password_can_be_retried(self):
        ready = self.make_signup(status=Signup.Status.READY)
        old = self.make_signup(password_hash='')
        for signup in (ready, old):
            response = self.platform.post(f'/api/v1/platform/signups/{signup.pk}/retry/')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OperatorFlagTests(OperatorTestCase):
    def test_me_says_who_may_open_the_dashboard(self):
        self.assertTrue(self.platform.get('/api/v1/auth/me/').data['is_platform_operator'])
        superuser_at_hospital = make_user(Role.ADMIN)
        superuser_at_hospital.is_superuser = True
        superuser_at_hospital.save()
        self.client.force_authenticate(superuser_at_hospital)
        self.assertFalse(self.client.get('/api/v1/auth/me/').data['is_platform_operator'])
