from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core import mail
from django.utils import timezone
from rest_framework import status

from authentication.models import User
from authentication.permissions import Role
from helpers.testing import TenantAPITestCase, make_user
from tenants.models import Hospital

from . import emails
from .inbox import Level, emails_paused, notify
from .models import Notification

LAGOS = ZoneInfo('Africa/Lagos')


class EmailTestCase(TenantAPITestCase):
    def setUp(self):
        Hospital.objects.filter(pk=self.tenant.pk).update(timezone='Africa/Lagos')
        self.hospital = Hospital.objects.get(pk=self.tenant.pk)
        self.doctor = make_user(Role.DOCTOR)

    def alert(self, user=None, **fields):
        defaults = {
            'kind': 'clinical.emergency_arrival', 'title': 'Emergency: Adaeze Okafor', 'level': Level.URGENT,
            'link': '/visits/7',
        }  # fmt: skip
        return notify([user or self.doctor], **{**defaults, **fields})


class ImportantEmailTests(EmailTestCase):
    def test_urgent_notifications_are_emailed_without_patient_details(self):
        self.alert()
        [email] = mail.outbox
        self.assertEqual(email.to, [self.doctor.email])
        self.assertEqual(email.subject, 'Urgent: An emergency patient has arrived')
        self.assertNotIn('Adaeze', email.subject + email.body)  # names stay behind the login
        self.assertIn('/visits/7', email.body)
        self.assertTrue(email.body.split('Open it: ')[1].startswith('http'))
        self.assertIsNotNone(Notification.objects.get().emailed_at)

    def test_routine_notifications_wait_for_the_summary(self):
        self.alert(kind='clinical.visit_opened', title='Ada is waiting', level=Level.INFO)
        self.assertEqual(mail.outbox, [])

    def test_subscription_notices_are_sent_in_full(self):
        admin = make_user(Role.ADMIN)
        notify([admin], kind='subscription.trial_ends_x_3', title='Your free trial ends in 3 days',
               body='Choose a plan to keep everything running.', link='/subscription', level=Level.WARNING)  # fmt: skip
        self.assertEqual(mail.outbox[0].subject, 'Your free trial ends in 3 days')
        self.assertIn('Choose a plan', mail.outbox[0].body)

    def test_preferences_are_respected(self):
        User.objects.filter(pk=self.doctor.pk).update(email_notifications=User.EmailNotifications.OFF)
        self.alert()
        careful = make_user(Role.NURSE)
        User.objects.filter(pk=careful.pk).update(email_notifications=User.EmailNotifications.IMPORTANT)
        self.alert(careful)
        self.assertEqual([email.to for email in mail.outbox], [[careful.email]])

    def test_demo_data_emails_nobody(self):
        with emails_paused():
            self.alert()
        self.assertEqual(mail.outbox, [])


class DailySummaryTests(EmailTestCase):
    def morning(self, hour=8):
        return timezone.now().astimezone(LAGOS).replace(hour=hour, minute=0)

    def test_one_summary_a_day_listing_what_is_unread(self):
        self.alert(kind='clinical.visit_opened', title='Ada is waiting', level=Level.INFO)
        self.alert(kind='lab.order_completed', title='Lab results ready: Ada', level=Level.INFO, link='/visits/8')
        read = self.alert(kind='clinical.prescribed', title='Rx', level=Level.INFO, link='/pharmacy')[0]
        Notification.objects.filter(pk=read.pk).update(read_at=timezone.now())

        self.assertEqual(emails.send_digests(self.hospital, now=self.morning(hour=6)), 0)  # too early
        self.assertEqual(emails.send_digests(self.hospital, now=self.morning()), 1)
        [email] = mail.outbox
        self.assertEqual(email.subject, 'Test Hospital: 2 notifications waiting')
        self.assertIn('A patient is waiting to see you', email.body)
        self.assertIn('Lab results are ready', email.body)
        self.assertNotIn('Ada', email.body)
        self.assertEqual(emails.send_digests(self.hospital, now=self.morning() + timedelta(hours=1)), 0)  # once a day

    def test_nothing_waiting_means_no_email(self):
        self.assertEqual(emails.send_digests(self.hospital, now=self.morning()), 0)
        self.assertEqual(mail.outbox, [])

    def test_important_only_people_get_no_summary(self):
        User.objects.filter(pk=self.doctor.pk).update(email_notifications=User.EmailNotifications.IMPORTANT)
        self.alert(kind='clinical.visit_opened', title='Ada is waiting', level=Level.INFO)
        self.assertEqual(emails.send_digests(self.hospital, now=self.morning()), 0)

    def test_urgent_alerts_already_emailed_are_not_repeated(self):
        self.alert()
        mail.outbox.clear()
        self.assertEqual(emails.send_digests(self.hospital, now=self.morning()), 0)


class PreferenceApiTests(EmailTestCase):
    def test_people_choose_their_emails(self):
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get('/api/v1/auth/me/').data['email_notifications'], 'all')
        response = self.client.patch('/api/v1/auth/me/', {'email_notifications': 'important'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.client.patch('/api/v1/auth/me/', {'email_notifications': 'spam'}).status_code, 400)
