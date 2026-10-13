from django.db import DatabaseError, transaction
from rest_framework import status
from rest_framework.test import APITestCase

from audit import events
from audit.models import AuditEvent
from audit.recorder import Category, record
from authentication.models import User
from clinical.models import Prescription, Visit
from helpers.testing import TEST_PASSWORD, make_consultation, make_user
from lab.models import LabTest
from lab.services import place_order
from pharmacy.models import Drug

Role = User.UserType


class ChangeTrackingTests(APITestCase):
    def setUp(self):
        self.receptionist = make_user(Role.RECEPTIONIST)
        self.doctor = make_user(Role.DOCTOR)
        self.patient = make_user(Role.PATIENT).patientprofile
        self.client.force_authenticate(self.receptionist)

    def open_visit(self, **headers):
        return self.client.post('/api/visits/', {
            'patient': self.patient.id, 'assigned_doctor': self.doctor.doctorprofile.id, 'reason_for_visit': 'Cough',
        }, **headers)

    def test_create_is_recorded_with_actor_patient_and_request(self):
        response = self.open_visit(HTTP_X_REQUEST_ID='req-12345678', HTTP_USER_AGENT='FrontDesk/1.0')

        event = AuditEvent.objects.get(action='create', resource_type='clinical.visit')
        self.assertEqual(event.actor_id, self.receptionist.id)
        self.assertEqual(event.actor_role, 'receptionist')
        self.assertEqual(event.patient_id, self.patient.id)
        self.assertEqual(event.changes['reason_for_visit'], [None, 'Cough'])
        self.assertEqual(event.request_id, 'req-12345678')
        self.assertEqual(event.user_agent, 'FrontDesk/1.0')
        self.assertEqual(response['X-Request-ID'], 'req-12345678')

    def test_bad_request_id_is_replaced(self):
        response = self.open_visit(HTTP_X_REQUEST_ID='<script>')
        self.assertRegex(response['X-Request-ID'], r'^[0-9a-f]{32}$')

    def test_update_records_only_changed_fields(self):
        visit_id = self.open_visit().data['id']
        self.client.patch(f'/api/visits/{visit_id}/', {'status': 'completed'})

        event = AuditEvent.objects.get(action='update', resource_type='clinical.visit')
        self.assertEqual(event.changes, {'status': ['in_progress', 'completed']})

    def test_unchanged_save_is_not_recorded(self):
        visit = Visit.objects.get(pk=self.open_visit().data['id'])
        visit.save()
        self.assertFalse(AuditEvent.objects.filter(action='update').exists())

    def test_passwords_are_redacted(self):
        self.client.post('/api/create-profile/patients/', {
            'user': {'email': 'new@example.com', 'password': 'Sup3r-secret-pw', 'first_name': 'N', 'last_name': 'P'}
        }, format='json')
        new_user = User.objects.get(email='new@example.com')
        event = AuditEvent.objects.get(action='create', resource_type='authentication.user', resource_id=str(new_user.id))
        self.assertEqual(event.changes['password'], ['***', '***'])
        self.assertNotIn('Sup3r-secret-pw', str(event.changes))


class AccessLoggingTests(APITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR)
        self.consultation = make_consultation(doctor=self.doctor)
        self.patient_id = self.consultation.visit.patient_id
        self.client.force_authenticate(self.doctor)

    def test_viewing_a_record_is_logged(self):
        self.client.get(f'/api/consultations/{self.consultation.id}/')
        event = AuditEvent.objects.get(action='view')
        self.assertEqual((event.resource_type, event.resource_id), ('clinical.consultation', str(self.consultation.id)))
        self.assertEqual(event.patient_id, self.patient_id)

    def test_listing_logs_ids_and_patients_on_page(self):
        self.client.get('/api/visits/?page=1')
        event = AuditEvent.objects.get(action='list', resource_type='clinical.visit')
        self.assertEqual(event.metadata['ids'], [self.consultation.visit_id])
        self.assertEqual(event.metadata['patient_ids'], [self.patient_id])
        self.assertEqual(event.metadata['query'], {'page': '1'})

    def test_admin_can_trace_everyone_who_saw_a_patient(self):
        self.client.get('/api/visits/')
        self.client.get(f'/api/consultations/{self.consultation.id}/')

        self.client.force_authenticate(make_user(Role.ADMIN))
        response = self.client.get(f'/api/audit/events/?patient={self.patient_id}&category=data_access')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({e['action'] for e in response.data['results']}, {'list', 'view'})
        self.assertEqual({e['actor_id'] for e in response.data['results']}, {self.doctor.id})

    def test_audit_log_is_admin_only(self):
        self.assertEqual(self.client.get('/api/audit/events/').status_code, status.HTTP_403_FORBIDDEN)


class SecurityEventTests(APITestCase):
    def setUp(self):
        self.user = make_user(Role.NURSE)

    def login(self, password):
        return self.client.post('/api/auth/login/', {'email': self.user.email, 'password': password})

    def actions(self):
        return list(AuditEvent.objects.filter(category=Category.SECURITY).order_by('id').values_list('action', flat=True))

    def test_login_success_and_failure(self):
        self.login('wrong')
        self.login(TEST_PASSWORD)
        self.assertEqual(self.actions(), ['login_failed', 'login'])
        self.assertEqual(AuditEvent.objects.get(action='login').actor_id, self.user.id)

    def test_unknown_email_is_logged(self):
        self.client.post('/api/auth/login/', {'email': 'nobody@example.com', 'password': 'x'})
        event = AuditEvent.objects.get(action='login_failed')
        self.assertIsNone(event.actor_id)
        self.assertEqual(event.metadata['email'], 'nobody@example.com')

    def test_lockout_is_logged(self):
        for _ in range(5):
            self.login('wrong')
        self.login(TEST_PASSWORD)
        self.assertEqual(self.actions()[-2:], ['account_locked', 'login_blocked'])

    def test_permission_denied_is_logged(self):
        self.client.force_authenticate(self.user)
        self.client.post('/api/pharmacy/drugs/', {'name': 'X'})
        event = AuditEvent.objects.get(action='permission_denied')
        self.assertEqual((event.actor_id, event.metadata['path']), (self.user.id, '/api/pharmacy/drugs/'))


class DomainEventTests(APITestCase):
    def setUp(self):
        self.received = []

    def listen(self, name):
        handler = events.subscribe(name)(self.received.append)
        self.addCleanup(events._subscribers[name].remove, handler)

    def test_events_are_delivered_after_commit(self):
        self.listen('lab.result_completed')
        labtech = make_user(Role.LAB_TECHNICIAN)
        consultation = make_consultation()
        order = place_order(patient=consultation.visit.patient, consultation=consultation,
                            tests=[LabTest.objects.create(name='FBC', cost=1)])
        result = order.results.get()

        self.client.force_authenticate(labtech)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.client.patch(f'/api/lab/test-results/{result.id}/', {'status': 'completed', 'result_value': 'OK'})
            self.assertEqual(self.received, [])  # nothing before commit

        self.assertTrue(callbacks)
        [event] = self.received
        self.assertEqual((event.name, event.resource.pk), ('lab.result_completed', result.pk))
        self.assertTrue(AuditEvent.objects.filter(action='lab.order_completed', patient_id=order.patient_id).exists())

    def test_failing_subscriber_does_not_break_others(self):
        def broken(event):
            raise RuntimeError('boom')

        events.subscribe('test.event')(broken)
        self.addCleanup(events._subscribers['test.event'].remove, broken)
        self.listen('test.event')

        with self.assertLogs('hms.events', level='ERROR'), self.captureOnCommitCallbacks(execute=True):
            events.publish('test.event', value=1)
        self.assertEqual(len(self.received), 1)

    def test_dispensing_audits_stock_and_flags_low_stock(self):
        drug = Drug.objects.create(name='Paracetamol', quantity_in_stock=12, reorder_level=5)
        prescription = Prescription.objects.create(
            consultation=make_consultation(), drug=drug, medication_name='Paracetamol',
            dosage='1g', frequency='TDS', duration='3 days',
        )
        self.client.force_authenticate(make_user(Role.PHARMACIST))
        self.client.post('/api/pharmacy/dispense-transactions/', {
            'items': [{'prescription': prescription.id, 'drug': drug.id, 'quantity_dispensed': 9}]
        }, format='json')

        stock_change = AuditEvent.objects.get(action='update', resource_type='pharmacy.drug')
        self.assertEqual(stock_change.changes, {'quantity_in_stock': [12, 3]})
        self.assertTrue(AuditEvent.objects.filter(action='pharmacy.stock_low', resource_id=str(drug.id)).exists())
        dispensed = AuditEvent.objects.get(action='pharmacy.dispensed')
        self.assertEqual(dispensed.patient_id, prescription.consultation.visit.patient_id)


class AppendOnlyTests(APITestCase):
    def test_events_cannot_be_changed_or_deleted(self):
        event = record('test', Category.SECURITY)

        with self.assertRaises(PermissionError):
            event.save()
        with self.assertRaises(PermissionError):
            event.delete()
        # Raw/bulk SQL is stopped by the database trigger
        for attempt in (lambda: AuditEvent.objects.filter(pk=event.pk).update(action='x'),
                        lambda: AuditEvent.objects.filter(pk=event.pk).delete()):
            with self.assertRaises(DatabaseError), transaction.atomic():
                attempt()

        self.assertEqual(AuditEvent.objects.get(pk=event.pk).action, 'test')
