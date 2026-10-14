from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework import status

from audit.models import AuditEvent
from authentication.models import User
from clinical import vitals as rules
from clinical.models import Visit
from helpers.testing import TenantAPITestCase, make_consultation, make_user

Role = User.UserType


class VitalRulesTests(SimpleTestCase):
    def test_flags_and_criticality(self):
        self.assertEqual(rules.assess({'temperature_c': Decimal('38.4')}), (['fever'], False))
        self.assertEqual(rules.assess({'spo2_percent': 86}), (['very low oxygen saturation'], True))
        flags, critical = rules.assess({'systolic_bp': 150, 'diastolic_bp': 95})
        self.assertEqual((flags, critical), (['high blood pressure'], False))  # reported once
        self.assertEqual(rules.assess({'pulse_bpm': 72, 'spo2_percent': 98}), ([], False))

    def test_implausible_values(self):
        errors = rules.implausible({'temperature_c': Decimal('375'), 'systolic_bp': 80, 'diastolic_bp': 90})
        self.assertEqual(set(errors), {'temperature_c', 'diastolic_bp'})


class VitalsApiTests(TenantAPITestCase):
    def setUp(self):
        self.visit = make_consultation().visit
        self.nurse = make_user(Role.NURSE)
        self.client.force_authenticate(self.nurse)

    def record(self, **readings):
        return self.client.post('/api/v1/vitals/', {'visit': self.visit.id, **readings})

    def test_nurse_records_vitals_with_bmi_and_flags(self):
        response = self.record(temperature_c='38.6', pulse_bpm=110, weight_kg='70', height_cm='175')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['bmi'], 22.9)
        self.assertEqual(response.data['flags'], ['fever', 'fast pulse'])
        self.assertFalse(response.data['is_critical'])
        self.assertEqual(response.data['recorded_by_name'], self.nurse.get_full_name())

    def test_critical_vitals_raise_an_event(self):
        self.record(spo2_percent=85)
        event = AuditEvent.objects.get(action='clinical.critical_vitals')
        self.assertEqual(event.patient_id, self.visit.patient_id)
        self.assertIn('very low oxygen saturation', event.metadata['flags'])

    def test_rejects_empty_and_implausible_readings(self):
        self.assertEqual(self.record().status_code, status.HTTP_400_BAD_REQUEST)
        response = self.record(systolic_bp=80, diastolic_bp=110)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('diastolic_bp', response.data)

    def test_vitals_are_immutable_and_scoped(self):
        vitals_id = self.record(pulse_bpm=80).data['id']
        self.assertEqual(self.client.patch(f'/api/v1/vitals/{vitals_id}/', {'pulse_bpm': 90}).status_code, 405)

        # Another doctor can neither see nor add to this patient's vitals
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.client.get('/api/v1/vitals/').data['count'], 0)
        self.assertEqual(self.record(pulse_bpm=80).status_code, status.HTTP_400_BAD_REQUEST)

        # The assigned doctor sees them inside the visit
        self.client.force_authenticate(self.visit.assigned_doctor.user)
        visit = self.client.get(f'/api/v1/visits/{self.visit.id}/').data
        self.assertEqual([v['id'] for v in visit['vitals']], [vitals_id])

    def test_patient_history_for_charting(self):
        self.record(weight_kg='70')
        later_visit = make_consultation(doctor=self.visit.assigned_doctor.user, patient=self.visit.patient.user).visit
        self.client.post('/api/v1/vitals/', {'visit': later_visit.id, 'weight_kg': '72'})
        history = self.client.get('/api/v1/vitals/', {'patient': self.visit.patient_id, 'ordering': 'recorded_at'})
        self.assertEqual([v['weight_kg'] for v in history.data['results']], ['70.00', '72.00'])


class TriageTests(TenantAPITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR).doctorprofile
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        self.first, self.second, self.third = (self.walk_in() for _ in range(3))
        self.client.force_authenticate(make_user(Role.NURSE))

    def walk_in(self):
        response = self.client.post('/api/v1/visits/', {
            'patient': make_user(Role.PATIENT).patientprofile.id,
            'assigned_doctor': self.doctor.id,
            'reason_for_visit': 'Unwell',
        })  # fmt: skip
        return Visit.objects.get(pk=response.data['id'])

    def triage(self, visit, level, **extra):
        return self.client.post(f'/api/v1/visits/{visit.id}/triage/', {'triage_level': level, **extra})

    def test_emergencies_jump_the_queue(self):
        self.triage(self.third, 'emergency', triage_notes='Chest pain')
        self.triage(self.first, 'non_urgent')

        queue = self.client.get('/api/v1/queue/').data
        self.assertEqual([e['id'] for e in queue], [self.third.id, self.second.id, self.first.id])
        self.assertEqual([e['position'] for e in queue], [1, 2, 3])
        self.assertEqual(queue[0]['triage_level'], 'emergency')
        self.assertTrue(AuditEvent.objects.filter(action='clinical.emergency_arrival').exists())

    def test_who_can_triage(self):
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        self.assertEqual(self.triage(self.first, 'urgent').status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.doctor.user)
        self.assertEqual(self.triage(self.first, 'urgent').data['triage_level'], 'urgent')

    def test_only_patients_in_the_queue_are_triaged(self):
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        self.client.post(f'/api/v1/visits/{self.first.id}/cancel/')
        self.client.force_authenticate(make_user(Role.NURSE))
        self.assertEqual(self.triage(self.first, 'urgent').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.triage(self.second, 'critical').status_code, status.HTTP_400_BAD_REQUEST)
