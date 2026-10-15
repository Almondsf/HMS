from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework import status

from audit import events
from authentication.permissions import Role
from billing.models import ServiceItem
from clinical import services as clinical
from helpers.testing import TenantAPITestCase, make_user
from lab import services as lab
from lab.models import LabTest
from pharmacy.models import Drug
from profiles.models import RecordSequence
from subscriptions import services as subscriptions
from subscriptions.models import Subscription
from tenants.management.commands.seed_demo import SEED_MARKER

from . import inbox
from .models import Notification


class AlertTestCase(TenantAPITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR)
        self.nurse = make_user(Role.NURSE)
        self.pharmacist = make_user(Role.PHARMACIST)
        self.cashier = make_user(Role.CASHIER)
        self.lab_tech = make_user(Role.LAB_TECHNICIAN)
        self.admin = make_user(Role.ADMIN)
        self.patient = make_user(Role.PATIENT)

    def inbox_of(self, user):
        return list(Notification.objects.filter(recipient=user))

    def open_visit(self):
        with self.captureOnCommitCallbacks(execute=True):
            return clinical.open_visit(
                patient=self.patient.patientprofile, assigned_doctor=self.doctor.doctorprofile, reason_for_visit='Fever'
            )


class ClinicalAlertTests(AlertTestCase):
    def test_doctor_hears_when_a_patient_is_waiting(self):
        visit = self.open_visit()
        [notification] = self.inbox_of(self.doctor)
        self.assertIn('is waiting to see you', notification.title)
        self.assertEqual(notification.link, f'/visits/{visit.pk}')
        self.assertEqual(self.inbox_of(self.nurse), [])

    def test_emergencies_reach_the_doctor_and_nurses_urgently(self):
        visit = self.open_visit()
        with self.captureOnCommitCallbacks(execute=True):
            clinical.triage(visit=visit, by=self.nurse, level='emergency')
        doctor_alerts = [n for n in self.inbox_of(self.doctor) if n.kind == 'clinical.emergency_arrival']
        self.assertEqual(doctor_alerts[0].level, Notification.Level.URGENT)
        self.assertEqual(len(self.inbox_of(self.nurse)), 1)

    def test_pharmacists_hear_about_prescriptions_only(self):
        visit = self.open_visit()
        with self.captureOnCommitCallbacks(execute=True):
            clinical.record_consultation(doctor_user=self.doctor, visit=visit, subjective='Cough')
        self.assertEqual(self.inbox_of(self.pharmacist), [])
        with self.captureOnCommitCallbacks(execute=True):
            clinical.record_consultation(
                doctor_user=self.doctor, visit=visit,
                prescriptions=[{'medication_name': 'Amoxicillin', 'dosage': '500mg', 'frequency': 'tds',
                                'duration': '5 days', 'quantity': 15}],
            )  # fmt: skip
        [notification] = self.inbox_of(self.pharmacist)
        self.assertIn('New prescription', notification.title)
        self.assertEqual(notification.link, '/pharmacy')

    def test_cashiers_hear_when_a_patient_is_ready_to_pay(self):
        ServiceItem.objects.create(code='CARD', name='Card', price=2000, charge_on='visit_opened')
        visit = self.open_visit()
        with self.captureOnCommitCallbacks(execute=True):
            clinical.complete_visit(visit=visit, by=self.doctor)
        [notification] = self.inbox_of(self.cashier)
        self.assertIn('ready to pay', notification.title)
        self.assertTrue(notification.link.startswith('/billing/invoices/'))


class OtherAlertTests(AlertTestCase):
    def test_ordering_doctor_hears_when_results_are_ready(self):
        test = LabTest.objects.create(name='Malaria parasite', cost=1500)
        with self.captureOnCommitCallbacks(execute=True):
            order = lab.place_order(
                patient=self.patient.patientprofile, tests=[test], ordered_by=self.doctor.doctorprofile
            )
        self.assertEqual(len(self.inbox_of(self.lab_tech)), 1)
        with self.captureOnCommitCallbacks(execute=True):
            events.publish('lab.order_completed', resource=order)
        [notification] = self.inbox_of(self.doctor)
        self.assertIn('Lab results ready', notification.title)

    def test_low_stock_does_not_pile_up_while_unread(self):
        drug = Drug.objects.create(name='Paracetamol', quantity_in_stock=3, reorder_level=10, unit_price=50)
        for _ in range(3):
            with self.captureOnCommitCallbacks(execute=True):
                events.publish('pharmacy.stock_low', resource=drug, quantity_in_stock=3, reorder_level=10)
        self.assertEqual(len(self.inbox_of(self.pharmacist)), 1)
        self.assertEqual(len(self.inbox_of(self.admin)), 1)
        Notification.objects.update(read_at=timezone.now())
        with self.captureOnCommitCallbacks(execute=True):
            events.publish('pharmacy.stock_low', resource=drug, quantity_in_stock=2, reorder_level=10)
        self.assertEqual(len(self.inbox_of(self.pharmacist)), 2)  # read ones don't block a new alert

    def test_nobody_is_told_about_their_own_action(self):
        with patch('notifications.inbox.context.current_user', return_value=self.pharmacist):
            inbox.notify(inbox.staff(Role.PHARMACIST, Role.ADMIN), kind='test', title='Hello')
        self.assertEqual(self.inbox_of(self.pharmacist), [])
        self.assertEqual(len(self.inbox_of(self.admin)), 1)

    def test_inactive_staff_get_nothing(self):
        self.nurse.is_active = False
        self.nurse.save()
        inbox.notify(inbox.staff(Role.NURSE), kind='test', title='Hello')
        self.assertFalse(Notification.objects.exists())


class NotificationApiTests(AlertTestCase):
    def setUp(self):
        super().setUp()
        inbox.notify([self.doctor], kind='a', title='First')
        inbox.notify([self.doctor], kind='b', title='Second')
        inbox.notify([self.nurse], kind='c', title='Not yours')
        self.client.force_authenticate(self.doctor)

    def test_people_see_only_their_own(self):
        titles = [row['title'] for row in self.client.get('/api/v1/notifications/').data['results']]
        self.assertEqual(sorted(titles), ['First', 'Second'])
        self.assertEqual(self.client.get('/api/v1/notifications/unread-count/').data['count'], 2)
        theirs = Notification.objects.get(recipient=self.nurse)
        self.assertEqual(self.client.post(f'/api/v1/notifications/{theirs.pk}/read/').status_code, 404)

    def test_mark_read(self):
        first = Notification.objects.get(title='First')
        self.assertTrue(self.client.post(f'/api/v1/notifications/{first.pk}/read/').data['is_read'])
        self.assertEqual(len(self.client.get('/api/v1/notifications/', {'unread': 'true'}).data['results']), 1)
        self.assertEqual(self.client.post('/api/v1/notifications/read-all/').data['marked_read'], 1)
        self.assertEqual(self.client.get('/api/v1/notifications/unread-count/').data['count'], 0)

    def test_works_when_the_hospital_is_read_only(self):
        subscriptions.start_trial(self.tenant)
        Subscription.objects.filter(hospital=self.tenant).update(current_period_end=timezone.now() - timedelta(days=60))
        self.assertEqual(self.client.post('/api/v1/notifications/read-all/').status_code, status.HTTP_200_OK)


class SeedNotificationsTests(AlertTestCase):
    def test_refuses_hospitals_without_demo_data(self):
        with self.assertRaisesMessage(CommandError, 'no demo data'):
            call_command('seed_notifications', schema=self.tenant.schema_name, stdout=StringIO())
        self.assertFalse(Notification.objects.exists())

    def test_fills_a_demo_hospital_through_the_real_handlers(self):
        RecordSequence.objects.create(name=SEED_MARKER, last_value=1)
        self.open_visit()
        Notification.objects.all().delete()
        call_command('seed_notifications', schema=self.tenant.schema_name, stdout=StringIO())
        self.assertTrue(any('is waiting to see you' in n.title for n in self.inbox_of(self.doctor)))
        self.assertEqual(len(self.inbox_of(self.admin)), 1)  # the trial notice


class SubscriptionNoticeTests(AlertTestCase):
    def notices(self):
        call_command('notify_subscription_status', stdout=StringIO())
        return [n for n in self.inbox_of(self.admin) if n.kind.startswith('subscription.')]

    def set_period_end(self, delta):
        subscriptions.start_trial(self.tenant)
        Subscription.objects.filter(hospital=self.tenant).update(current_period_end=timezone.now() + delta)

    def test_trial_ending_is_announced_once_per_milestone(self):
        self.set_period_end(timedelta(days=3, hours=2))
        [notice] = self.notices()
        self.assertIn('ends in 3 days', notice.title)
        Notification.objects.update(read_at=timezone.now())
        self.assertEqual(len(self.notices()), 1)  # not again, even after it was read

    def test_no_notice_far_from_the_end(self):
        self.set_period_end(timedelta(days=10, hours=2))
        self.assertEqual(self.notices(), [])

    def test_overdue_and_lapsed(self):
        self.set_period_end(-timedelta(days=2))
        self.assertEqual(self.notices()[0].level, Notification.Level.WARNING)
        Notification.objects.all().delete()
        self.set_period_end(-timedelta(days=30))
        self.assertEqual(self.notices()[0].level, Notification.Level.URGENT)
