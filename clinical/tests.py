from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from clinical.models import Visit, Consultation
from helpers.testing import make_user

Role = User.UserType


class ClinicalAccessTests(APITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR)
        self.other_doctor = make_user(Role.DOCTOR)
        self.patient = make_user(Role.PATIENT)
        self.other_patient = make_user(Role.PATIENT)
        self.receptionist = make_user(Role.RECEPTIONIST)

        self.my_visit = Visit.objects.create(
            patient=self.patient.patientprofile,
            assigned_doctor=self.doctor.doctorprofile,
            reason_for_visit='Headache',
        )
        self.other_visit = Visit.objects.create(
            patient=self.other_patient.patientprofile,
            assigned_doctor=self.other_doctor.doctorprofile,
            reason_for_visit='Fever',
        )
        self.my_consultation = Consultation.objects.create(visit=self.my_visit, assessment='Migraine')
        Consultation.objects.create(visit=self.other_visit, assessment='Malaria')

    def ids(self, response):
        return {item['id'] for item in response.data['results']}

    def test_doctor_sees_only_own_visits_and_consultations(self):
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.ids(self.client.get('/api/visits/')), {self.my_visit.id})
        self.assertEqual(self.ids(self.client.get('/api/consultations/')), {self.my_consultation.id})

    def test_patient_sees_only_own_records_and_cannot_write(self):
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.ids(self.client.get('/api/visits/')), {self.my_visit.id})
        self.assertEqual(self.ids(self.client.get('/api/consultations/')), {self.my_consultation.id})

        response = self.client.post('/api/visits/', {
            'patient': self.patient.patientprofile.id,
            'assigned_doctor': self.doctor.doctorprofile.id,
            'reason_for_visit': 'Self-booked',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_receptionist_does_not_see_clinical_notes(self):
        self.client.force_authenticate(self.receptionist)
        response = self.client.get(f'/api/visits/{self.my_visit.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('consultations', response.data)

    def test_visits_cannot_be_deleted(self):
        self.client.force_authenticate(self.receptionist)
        response = self.client.delete(f'/api/visits/{self.my_visit.id}/')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_doctor_cannot_consult_on_another_doctors_visit(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            '/api/consultations/', {'visit': self.other_visit.id, 'assessment': 'x'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_move_consultation_to_another_doctors_visit(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.patch(
            f'/api/consultations/{self.my_consultation.id}/',
            {'visit': self.other_visit.id}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.my_consultation.refresh_from_db()
        self.assertEqual(self.my_consultation.visit, self.my_visit)
