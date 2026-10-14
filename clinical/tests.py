from rest_framework import status

from authentication.models import User
from clinical.models import Consultation, Prescription, Visit
from helpers.testing import TenantAPITestCase, make_user
from lab.models import LabTest
from pharmacy.models import Drug

Role = User.UserType


class ClinicalAccessTests(TenantAPITestCase):
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
        self.assertEqual(self.ids(self.client.get('/api/v1/visits/')), {self.my_visit.id})
        self.assertEqual(self.ids(self.client.get('/api/v1/consultations/')), {self.my_consultation.id})

    def test_patient_sees_only_own_records_and_cannot_write(self):
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.ids(self.client.get('/api/v1/visits/')), {self.my_visit.id})
        self.assertEqual(self.ids(self.client.get('/api/v1/consultations/')), {self.my_consultation.id})

        response = self.client.post(
            '/api/v1/visits/',
            {
                'patient': self.patient.patientprofile.id,
                'assigned_doctor': self.doctor.doctorprofile.id,
                'reason_for_visit': 'Self-booked',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_receptionist_does_not_see_clinical_notes(self):
        self.client.force_authenticate(self.receptionist)
        response = self.client.get(f'/api/v1/visits/{self.my_visit.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('consultations', response.data)

    def test_visits_cannot_be_deleted(self):
        self.client.force_authenticate(self.receptionist)
        response = self.client.delete(f'/api/v1/visits/{self.my_visit.id}/')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_doctor_cannot_consult_on_another_doctors_visit(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            '/api/v1/consultations/', {'visit': self.other_visit.id, 'assessment': 'x'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_move_consultation_to_another_doctors_visit(self):
        self.client.force_authenticate(self.doctor)
        response = self.client.patch(
            f'/api/v1/consultations/{self.my_consultation.id}/', {'visit': self.other_visit.id}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.my_consultation.refresh_from_db()
        self.assertEqual(self.my_consultation.visit, self.my_visit)


class ConsultationWorkflowTests(TenantAPITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR)
        self.patient = make_user(Role.PATIENT)
        self.visit = Visit.objects.create(
            patient=self.patient.patientprofile,
            assigned_doctor=self.doctor.doctorprofile,
            reason_for_visit='Fever',
        )
        self.drug = Drug.objects.create(name='Artemether', quantity_in_stock=50)
        self.test = LabTest.objects.create(name='Malaria parasite', cost=1500)
        self.client.force_authenticate(self.doctor)

    def test_consultation_creates_prescriptions_and_lab_order(self):
        response = self.client.post(
            '/api/v1/consultations/',
            {
                'visit': self.visit.id,
                'assessment': 'Suspected malaria',
                'prescriptions': [
                    {'drug': self.drug.id, 'dosage': '80mg', 'frequency': 'BD', 'duration': '3 days', 'quantity': 6},
                    {'medication_name': 'ORS sachet', 'dosage': '1', 'frequency': 'PRN', 'duration': '3 days'},
                ],
                'lab_tests': [self.test.id],
                'lab_reason': 'Confirm malaria',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        consultation = Consultation.objects.get(pk=response.data['id'])
        names = set(consultation.prescriptions.values_list('medication_name', flat=True))
        self.assertEqual(names, {'Artemether', 'ORS sachet'})

        order = consultation.lab_orders.get()
        self.assertEqual(order.patient, self.patient.patientprofile)
        self.assertEqual(order.ordered_by, self.doctor.doctorprofile)
        self.assertEqual(list(order.results.values_list('test__name', flat=True)), ['Malaria parasite'])
        self.assertEqual(len(response.data['lab_orders']), 1)

    def test_prescription_needs_drug_or_name(self):
        response = self.client.post(
            '/api/v1/consultations/',
            {
                'visit': self.visit.id,
                'prescriptions': [{'dosage': '1', 'frequency': 'OD', 'duration': '1 day'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Consultation.objects.exists())

    def test_prescriptions_cannot_be_added_on_update(self):
        consultation = Consultation.objects.create(visit=self.visit)
        response = self.client.patch(
            f'/api/v1/consultations/{consultation.id}/',
            {
                'prescriptions': [{'medication_name': 'X', 'dosage': '1', 'frequency': 'OD', 'duration': '1 day'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pharmacist_sees_prescription_queue(self):
        consultation = Consultation.objects.create(visit=self.visit)
        Prescription.objects.create(
            consultation=consultation,
            drug=self.drug,
            medication_name='Artemether',
            dosage='80mg',
            frequency='BD',
            duration='3 days',
        )
        self.client.force_authenticate(make_user(Role.PHARMACIST))

        response = self.client.get(f'/api/v1/prescriptions/?patient={self.patient.patientprofile.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        [item] = response.data['results']
        self.assertEqual(item['patient_name'], self.patient.get_full_name())
        self.assertEqual(item['quantity_dispensed'], 0)
