from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework import status

from authentication.models import User
from helpers.testing import TenantAPITestCase, make_consultation, make_user
from lab.models import LabTest, TestOrder, TestResult
from tenants.models import Hospital

Role = User.UserType


class LabWorkflowTests(TenantAPITestCase):
    def setUp(self):
        self.doctor = make_user(Role.DOCTOR)
        self.labtech = make_user(Role.LAB_TECHNICIAN)
        self.consultation = make_consultation(doctor=self.doctor)
        self.fbc = LabTest.objects.create(name='Full blood count', cost=3000)
        self.mp = LabTest.objects.create(name='Malaria parasite', cost=1500)

    def place_order(self, user, **data):
        self.client.force_authenticate(user)
        return self.client.post('/api/v1/lab/test-orders/', data, format='json')

    def record(self, result, **data):
        self.client.force_authenticate(self.labtech)
        return self.client.patch(f'/api/v1/lab/test-results/{result.id}/', data, format='json')

    def test_doctor_orders_tests_from_consultation(self):
        response = self.place_order(self.doctor, consultation=self.consultation.id, tests=[self.fbc.id, self.mp.id])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        order = TestOrder.objects.get(pk=response.data['id'])
        self.assertEqual(order.patient, self.consultation.visit.patient)
        self.assertEqual(order.ordered_by, self.doctor.doctorprofile)
        self.assertEqual(order.results.count(), 2)
        self.assertEqual(response.data['ordered_by_name'], self.doctor.get_full_name())

    def test_doctor_cannot_order_on_another_doctors_consultation(self):
        response = self.place_order(make_user(Role.DOCTOR), consultation=self.consultation.id, tests=[self.fbc.id])
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lab_tech_registers_walk_in_order(self):
        patient = make_user(Role.PATIENT).patientprofile
        response = self.place_order(self.labtech, patient=patient.id, tests=[self.fbc.id])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNone(TestOrder.objects.get().ordered_by)

    def test_retired_test_cannot_be_ordered(self):
        self.mp.is_active = False
        self.mp.save()
        response = self.place_order(self.doctor, consultation=self.consultation.id, tests=[self.mp.id])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_status_follows_results(self):
        self.place_order(self.doctor, consultation=self.consultation.id, tests=[self.fbc.id, self.mp.id])
        order = TestOrder.objects.get()
        fbc_result, mp_result = order.results.order_by('test__name')

        self.record(fbc_result, status='collected')
        order.refresh_from_db()
        self.assertEqual(order.status, TestOrder.Status.IN_PROGRESS)

        self.record(fbc_result, status='completed', result_value='Hb 13.2')
        self.record(mp_result, status='cancelled', notes='Sample haemolysed')
        order.refresh_from_db()
        self.assertEqual(order.status, TestOrder.Status.COMPLETED)

        fbc_result.refresh_from_db()
        self.assertEqual(fbc_result.labtech, self.labtech.labtechprofile)
        self.assertIsNotNone(fbc_result.completed_at)

    def test_completed_result_needs_value_and_is_final(self):
        self.place_order(self.doctor, consultation=self.consultation.id, tests=[self.fbc.id])
        result = TestResult.objects.get()

        self.assertEqual(self.record(result, status='completed').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.record(result, status='completed', result_value='Normal').status_code, 200)
        self.assertEqual(self.record(result, result_value='Changed').status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_sees_only_own_patients_results(self):
        self.place_order(self.doctor, consultation=self.consultation.id, tests=[self.fbc.id])
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.client.get('/api/v1/lab/test-results/').data['count'], 0)
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get('/api/v1/lab/test-results/').data['count'], 1)


class LegacyLabOrderMigrationTests(TransactionTestCase):
    '''clinical.LabTestOrder rows must survive the move into the lab module.'''

    # Everything else pinned to how it was when this migration shipped
    pinned = [('authentication', '0005_login_lockout'), ('profiles', '0003_alter_pharmacistprofile_user')]
    before = [('lab', '0003_lab_workflow'), ('clinical', '0002_rename_laborder_labtestorder'), *pinned]
    after = [('lab', '0004_copy_lab_data'), *pinned]

    def setUp(self):
        # A throwaway hospital schema to roll migrations back and forth in
        self.hospital = Hospital(schema_name='migration_test', name='Migration test')
        self.hospital.save(verbosity=0)
        connection.set_tenant(self.hospital)

    def tearDown(self):
        connection.set_schema_to_public()
        self.hospital.delete(force_drop=True)

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def test_legacy_orders_are_copied(self):
        apps = self.migrate(self.before)
        user = apps.get_model('authentication', 'User')
        doctor_user = user.objects.create(email='d@example.com', first_name='D', last_name='Doc', user_type='doctor')
        patient_user = user.objects.create(email='p@example.com', first_name='P', last_name='Pat')
        doctor = apps.get_model('profiles', 'DoctorProfile').objects.create(user=doctor_user, specialty='GP')
        patient = apps.get_model('profiles', 'PatientProfile').objects.create(user=patient_user)
        visit = apps.get_model('clinical', 'Visit').objects.create(
            patient=patient, assigned_doctor=doctor, reason_for_visit='Fever'
        )
        consultation = apps.get_model('clinical', 'Consultation').objects.create(visit=visit)
        apps.get_model('clinical', 'LabTestOrder').objects.create(
            consultation=consultation, test_name='Widal', reason='Typhoid?', status='completed'
        )

        apps = self.migrate(self.after)

        order = apps.get_model('lab', 'TestOrder').objects.get()
        self.assertEqual(
            (order.patient_id, order.ordered_by_id, order.consultation_id), (patient.id, doctor.id, consultation.id)
        )
        self.assertEqual((order.reason, order.status), ('Typhoid?', 'completed'))
        result = order.results.get()
        self.assertEqual((result.test.name, result.status), ('Widal', 'completed'))
