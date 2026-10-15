from datetime import datetime, time, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework import status

from authentication.permissions import Role
from helpers import sms
from helpers.testing import TenantAPITestCase, make_user
from scheduling import services as scheduling
from subscriptions import services as subscriptions
from subscriptions.models import Subscription
from tenants.models import Hospital

from . import services
from .models import SmsMessage

LAGOS = ZoneInfo('Africa/Lagos')


class NormalizeTests(SimpleTestCase):
    def test_nigerian_numbers_become_international(self):
        cases = {
            '0803 123 4567': '+2348031234567',
            '+234 803-123-4567': '+2348031234567',
            '2348031234567': '+2348031234567',
            '00233241234567': '+233241234567',
            '12345': None,
            '': None,
            None: None,
        }
        for number, expected in cases.items():
            with self.subTest(number):
                self.assertEqual(sms.normalize(number), expected)


class ProviderTests(SimpleTestCase):
    @override_settings(SMS_BACKEND='termii', SMS_API_KEY='key')
    def test_termii(self):
        with patch('helpers.sms._post', return_value={'message_id': '3017', 'message': 'Successfully Sent'}) as post:
            self.assertEqual(sms.send(to='+2348031234567', body='Hi', sender='STLUKES'), ('termii', '3017'))
        self.assertIn(b'"to": "2348031234567"', post.call_args.kwargs['data'])
        with patch('helpers.sms._post', return_value={'message': 'Insufficient balance'}):
            with self.assertRaisesMessage(sms.SmsError, 'Insufficient balance'):
                sms.send(to='+2348031234567', body='Hi')

    @override_settings(SMS_BACKEND='africastalking', SMS_API_KEY='key', SMS_USERNAME='hms')
    def test_africas_talking(self):
        ok = {'SMSMessageData': {'Recipients': [{'status': 'Success', 'messageId': 'ATX1'}]}}
        with patch('helpers.sms._post', return_value=ok):
            self.assertEqual(sms.send(to='+2348031234567', body='Hi'), ('africastalking', 'ATX1'))
        refused = {'SMSMessageData': {'Recipients': [{'status': 'InvalidPhoneNumber'}]}}
        with patch('helpers.sms._post', return_value=refused), self.assertRaises(sms.SmsError):
            sms.send(to='+2348031234567', body='Hi')

    def test_off_by_default(self):
        self.assertFalse(sms.available())
        with self.assertRaises(sms.SmsError):
            sms.send(to='+2348031234567', body='Hi')


class SmsTestCase(TenantAPITestCase):
    def setUp(self):
        override = override_settings(SMS_BACKEND='console')  # class-level overrides are skipped by the tenant test case
        override.enable()
        self.addCleanup(override.disable)
        Hospital.objects.filter(pk=self.tenant.pk).update(
            sms_booking_confirmations=True, sms_reminders=True, phone='0700 000 0000', timezone='Africa/Lagos'
        )
        self.doctor = make_user(Role.DOCTOR, specialty='General')
        self.doctor.last_name = 'Okafor'
        self.doctor.save()
        self.patient = make_user(Role.PATIENT)
        self.patient.phone_number = '08031234567'
        self.patient.save()
        sender = patch('helpers.sms.ConsoleBackend.send', return_value='msg-1')
        self.send = sender.start()
        self.addCleanup(sender.stop)

    def book(self, starts_at, patient=None):
        with self.captureOnCommitCallbacks(execute=True):
            return scheduling.book_appointment(
                patient=(patient or self.patient).patientprofile, doctor=self.doctor.doctorprofile, starts_at=starts_at
            )

    def tomorrow_at(self, hour, now=None):
        local = (now or timezone.now()).astimezone(LAGOS)
        return datetime.combine(local.date() + timedelta(days=1), time(hour), tzinfo=LAGOS)


class BookingConfirmationTests(SmsTestCase):
    def test_booking_sends_a_confirmation(self):
        appointment = self.book(self.tomorrow_at(10))
        message = SmsMessage.objects.get()
        self.assertEqual(message.status, SmsMessage.Status.SENT)
        self.assertEqual(message.to, '+2348031234567')
        self.assertIn('Test Hospital', message.body)
        self.assertIn('Dr Okafor', message.body)
        self.assertIn('at 10:00', message.body)  # in the hospital's time
        self.assertIn('call 0700 000 0000', message.body)
        self.assertEqual(message.appointment, appointment)
        self.send.assert_called_once()

    def test_nothing_is_sent_when_switched_off(self):
        Hospital.objects.filter(pk=self.tenant.pk).update(sms_booking_confirmations=False)
        self.book(self.tomorrow_at(10))
        self.assertFalse(SmsMessage.objects.exists())

    def test_opted_out_patients_and_missing_numbers_are_skipped_with_a_reason(self):
        self.patient.patientprofile.sms_opt_out = True
        self.patient.patientprofile.save()
        no_phone = make_user(Role.PATIENT)
        self.book(self.tomorrow_at(10))
        self.book(self.tomorrow_at(11), patient=no_phone)
        reasons = sorted(SmsMessage.objects.values_list('error', flat=True))
        self.assertEqual(reasons, ['No valid mobile number on file.', 'The patient asked not to get SMS.'])
        self.assertEqual(set(SmsMessage.objects.values_list('status', flat=True)), {SmsMessage.Status.SKIPPED})
        self.send.assert_not_called()

    def test_rescheduling_confirms_the_new_time(self):
        appointment = self.book(self.tomorrow_at(10))
        with self.captureOnCommitCallbacks(execute=True):
            scheduling.reschedule_appointment(appointment=appointment, starts_at=self.tomorrow_at(14))
        self.assertEqual(SmsMessage.objects.count(), 2)
        self.assertIn('at 14:00', SmsMessage.objects.first().body)

    def test_monthly_limit_caps_cost(self):
        with override_settings(SMS_MONTHLY_LIMIT_PER_HOSPITAL=1):
            self.book(self.tomorrow_at(10))
            self.book(self.tomorrow_at(11), patient=make_user(Role.PATIENT))
        latest = SmsMessage.objects.first()
        self.assertEqual(latest.status, SmsMessage.Status.SKIPPED)
        self.assertIn('limit', latest.error)

    def test_provider_failure_is_recorded(self):
        self.send.side_effect = sms.SmsError('Insufficient balance')
        self.book(self.tomorrow_at(10))
        message = SmsMessage.objects.get()
        self.assertEqual((message.status, message.error), (SmsMessage.Status.FAILED, 'Insufficient balance'))


class ReminderTests(SmsTestCase):
    def setUp(self):
        super().setUp()
        Hospital.objects.filter(pk=self.tenant.pk).update(sms_booking_confirmations=False)
        self.now = timezone.now().astimezone(LAGOS).replace(hour=10, minute=0)
        self.hospital = Hospital.objects.get(pk=self.tenant.pk)

    def test_reminders_go_out_once_for_tomorrow_only(self):
        tomorrow = self.book(self.tomorrow_at(9, self.now))
        self.book(self.tomorrow_at(9, self.now) + timedelta(days=1))  # the day after: not yet
        cancelled = self.book(self.tomorrow_at(15, self.now))
        scheduling.cancel_appointment(appointment=cancelled)

        self.assertEqual(services.send_due_reminders(self.hospital, now=self.now.replace(hour=7)), 0)  # too early
        self.assertEqual(services.send_due_reminders(self.hospital, now=self.now), 1)
        self.assertEqual(services.send_due_reminders(self.hospital, now=self.now + timedelta(hours=1)), 0)  # once
        reminder = SmsMessage.objects.get(kind=SmsMessage.Kind.REMINDER)
        self.assertEqual(reminder.appointment, tomorrow)
        self.assertIn('is tomorrow', reminder.body)

    def test_command_runs_for_enabled_hospitals_but_not_lapsed_ones(self):
        subscriptions.start_trial(self.tenant)
        with patch('notifications.services.send_due_reminders', return_value=0) as send:
            call_command('send_appointment_reminders', stdout=StringIO())
            self.assertEqual(send.call_count, 1)
            Subscription.objects.filter(hospital=self.tenant).update(
                current_period_end=timezone.now() - timedelta(days=30)
            )
            call_command('send_appointment_reminders', stdout=StringIO())
            self.assertEqual(send.call_count, 1)  # lapsed: skipped


class SettingsAndHistoryTests(SmsTestCase):
    def test_admin_switches_sms_on_with_a_valid_sender(self):
        self.client.force_authenticate(make_user(Role.ADMIN))
        data = self.client.get('/api/v1/hospital/').data
        self.assertTrue(data['sms_available'])
        ok = self.client.patch('/api/v1/hospital/', {'sms_reminders': False, 'sms_sender_id': 'STLUKES'})
        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(self.client.patch('/api/v1/hospital/', {'sms_sender_id': 'BAD!'}).status_code, 400)

    def test_front_desk_sees_messages_doctors_do_not(self):
        self.book(self.tomorrow_at(10))
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        rows = self.client.get('/api/v1/sms-messages/', {'patient': self.patient.patientprofile.pk}).data['results']
        self.assertEqual(len(rows), 1)
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.client.get('/api/v1/sms-messages/').status_code, status.HTTP_403_FORBIDDEN)
