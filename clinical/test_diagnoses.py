import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django_tenants.utils import schema_context
from rest_framework import status

from audit.models import AuditEvent
from authentication.models import User
from clinical.models import Diagnosis
from helpers.testing import TenantAPITestCase, make_consultation, make_user
from terminology.models import Icd10Code

Role = User.UserType


class DiagnosisTests(TenantAPITestCase):
    def setUp(self):
        self.consultation = make_consultation()
        self.doctor = self.consultation.visit.assigned_doctor.user
        self.client.force_authenticate(self.doctor)

    def diagnose(self, **fields):
        return self.client.post('/api/v1/diagnoses/', {'consultation': self.consultation.id, **fields})

    def test_coded_diagnosis_uses_the_icd_title(self):
        response = self.diagnose(code='B54')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['description'], 'Unspecified malaria')
        self.assertEqual((response.data['kind'], response.data['certainty']), ('primary', 'provisional'))
        self.assertTrue(AuditEvent.objects.filter(action='clinical.diagnosis_recorded').exists())

    def test_free_text_when_no_code_fits(self):
        response = self.diagnose(description='Suspected Lassa fever')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.diagnose().status_code, status.HTTP_400_BAD_REQUEST)  # neither code nor text

    def test_one_active_primary_diagnosis(self):
        malaria = self.diagnose(code='B54').data
        self.assertEqual(self.diagnose(code='A01.0').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.diagnose(code='A01.0', kind='secondary').status_code, status.HTTP_201_CREATED)

        # Lab results come back: rule malaria out, then typhoid can become primary
        ruled_out = self.client.patch(f"/api/v1/diagnoses/{malaria['id']}/", {'certainty': 'ruled_out'})
        self.assertEqual(ruled_out.status_code, status.HTTP_200_OK, ruled_out.data)
        typhoid = Diagnosis.objects.get(code='A01.0')
        confirmed = self.client.patch(f'/api/v1/diagnoses/{typhoid.id}/', {'kind': 'primary', 'certainty': 'confirmed'})
        self.assertEqual(confirmed.data['certainty'], 'confirmed')

    def test_retired_codes_cannot_be_used(self):
        with schema_context('public'):
            Icd10Code.objects.filter(code='J00').update(is_active=False)
        connection.set_tenant(self.tenant)
        self.assertEqual(self.diagnose(code='J00').status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_the_assigned_doctor_diagnoses(self):
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.diagnose(code='B54').status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(make_user(Role.NURSE))
        self.assertEqual(self.diagnose(code='B54').status_code, status.HTTP_403_FORBIDDEN)

    def test_diagnoses_inline_with_the_consultation(self):
        response = self.client.post('/api/v1/consultations/', {
            'visit': self.consultation.visit_id,
            'assessment': 'Hypertension with URTI',
            'diagnoses': [
                {'code': 'I10', 'certainty': 'confirmed'},
                {'code': 'J06.9', 'kind': 'secondary'},
            ],
        }, format='json')  # fmt: skip
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual([d['code'] for d in response.data['diagnoses']], ['I10', 'J06.9'])

        later = self.client.patch(
            f"/api/v1/consultations/{response.data['id']}/", {'diagnoses': [{'code': 'R51'}]}, format='json'
        )
        self.assertEqual(later.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patient_history_filter(self):
        self.diagnose(code='B54')
        other = make_consultation(doctor=self.doctor)
        self.client.post('/api/v1/diagnoses/', {'consultation': other.id, 'code': 'I10'})
        history = self.client.get('/api/v1/diagnoses/', {'patient': self.consultation.visit.patient_id})
        self.assertEqual([d['code'] for d in history.data['results']], ['B54'])


class Icd10LookupTests(TenantAPITestCase):
    def setUp(self):
        self.client.force_authenticate(make_user(Role.DOCTOR))

    def codes(self, term):
        return [c['code'] for c in self.client.get('/api/v1/icd10/', {'search': term}).data['results']]

    def test_search_by_title_and_code(self):
        self.assertIn('B50.9', self.codes('falciparum malaria'))
        self.assertEqual(self.codes('B50'), ['B50.9'])
        self.assertEqual(self.codes('b509'), ['B50.9'])  # without the dot
        self.assertEqual(
            self.client.get('/api/v1/icd10/B50.9/').data['title'], 'Plasmodium falciparum malaria, unspecified'
        )

    def test_patients_cannot_browse_codes(self):
        self.client.force_authenticate(make_user(Role.PATIENT))
        self.assertEqual(self.client.get('/api/v1/icd10/').status_code, status.HTTP_403_FORBIDDEN)


class LoadIcd10CommandTests(TenantAPITestCase):
    def test_loads_updates_and_retires_codes(self):
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, encoding='utf-8') as csv_file:
            csv_file.write(
                'code,title\nb54,Malaria (updated title)\nA00.0,"Cholera due to Vibrio cholerae 01, biovar cholerae"\n'
            )
        self.addCleanup(os.remove, csv_file.name)

        with schema_context('public'):
            call_command('load_icd10', csv_file.name, '--deactivate-missing', stdout=StringIO())
            self.assertEqual(Icd10Code.objects.get(code='B54').title, 'Malaria (updated title)')
            self.assertTrue(Icd10Code.objects.get(code='A00.0').is_active)
            self.assertFalse(Icd10Code.objects.get(code='I10').is_active)
        connection.set_tenant(self.tenant)
