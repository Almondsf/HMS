from rest_framework import status

from authentication.models import User
from helpers.testing import TEST_PASSWORD, TenantAPITestCase, make_user
from profiles.models import Department, PatientProfile, RecordSequence
from tenants.models import Hospital

Role = User.UserType


class PatientRegistryTests(TenantAPITestCase):
    def setUp(self):
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))

    def register(self, **fields):
        user = {'first_name': 'Ada', 'last_name': 'Obi', **fields.pop('user', {})}
        return self.client.post('/api/patients/', {'user': user, **fields}, format='json')

    def test_mrns_are_assigned_in_sequence_with_the_hospital_prefix(self):
        Hospital.objects.filter(pk=self.tenant.pk).update(mrn_prefix='TH')
        first, second = self.register().data['mrn'], self.register().data['mrn']
        self.assertRegex(first, r'^TH-\d{6}$')
        self.assertEqual(int(second.split('-')[1]), int(first.split('-')[1]) + 1)

    def test_existing_paper_record_number_is_kept_and_skipped_later(self):
        response = self.register(mrn='mrn-000777')
        self.assertEqual(response.data['mrn'], 'MRN-000777')
        RecordSequence.objects.update_or_create(name='mrn', defaults={'last_value': 776})
        self.assertEqual(self.register().data['mrn'], 'MRN-000778')  # 777 is already taken
        self.assertEqual(self.register(mrn='MRN-000777').status_code, status.HTTP_400_BAD_REQUEST)

    def test_mrn_cannot_be_changed(self):
        patient = self.register().data
        response = self.client.patch(f"/api/patients/{patient['id']}/", {'mrn': 'X-1'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patients_need_no_email_or_password(self):
        for _ in range(2):  # several email-less patients must not clash
            response = self.register(user={'phone_number': '+2348011111111'})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = PatientProfile.objects.get(pk=response.data['id']).user
        self.assertIsNone(user.email)
        self.assertFalse(user.has_usable_password())

    def test_staff_need_email_and_password(self):
        self.client.force_authenticate(make_user(Role.ADMIN))
        response = self.client.post(
            '/api/create-profile/nurses/', {'user': {'first_name': 'N', 'last_name': 'Urse'}}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data['user']), {'email', 'password'})

    def test_search_by_name_words_mrn_and_phone(self):
        ada = self.register(user={'phone_number': '+2348055550000'}).data
        self.register(user={'first_name': 'Bola', 'last_name': 'Obi'})
        self.register(user={'first_name': 'Ada', 'last_name': 'Eze'})

        def found(term):
            return {p['id'] for p in self.client.get('/api/patients/', {'search': term}).data['results']}

        self.assertEqual(found('ada obi'), {ada['id']})
        self.assertEqual(found(ada['mrn']), {ada['id']})
        self.assertEqual(found('55550000'), {ada['id']})
        self.assertEqual(len(found('obi')), 2)

    def test_update_keeps_own_email_and_changes_details(self):
        patient = self.register(user={'email': 'ada@example.com'}).data
        response = self.client.patch(
            f"/api/patients/{patient['id']}/",
            {'user': {'email': 'ada@example.com', 'phone_number': '+2348099999999'}, 'genotype': 'AS'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['user']['phone_number'], '+2348099999999')
        self.assertEqual(response.data['genotype'], 'AS')

    def test_who_can_see_and_change_patients(self):
        patient_user = make_user(Role.PATIENT)
        make_user(Role.PATIENT)

        self.client.force_authenticate(patient_user)
        [own] = self.client.get('/api/patients/').data['results']
        self.assertEqual(own['id'], patient_user.patientprofile.id)

        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertGreaterEqual(self.client.get('/api/patients/').data['count'], 2)
        self.assertEqual(self.register().status_code, status.HTTP_403_FORBIDDEN)


class StaffDirectoryTests(TenantAPITestCase):
    def setUp(self):
        self.admin = make_user(Role.ADMIN)
        self.paediatrics = Department.objects.create(name='Paediatrics')
        self.doctor = make_user(Role.DOCTOR, department=self.paediatrics)
        self.nurse = make_user(Role.NURSE)

    def test_receptionist_finds_doctors_by_role_and_department(self):
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        doctors = self.client.get('/api/staff/', {'role': 'doctor'}).data['results']
        self.assertEqual([d['id'] for d in doctors], [self.doctor.id])
        self.assertEqual(doctors[0]['department'], {'id': self.paediatrics.id, 'name': 'Paediatrics'})

        in_department = self.client.get('/api/staff/', {'department': self.paediatrics.id}).data['results']
        self.assertEqual([d['id'] for d in in_department], [self.doctor.id])

    def test_patients_cannot_browse_staff(self):
        self.client.force_authenticate(make_user(Role.PATIENT))
        self.assertEqual(self.client.get('/api/staff/').status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_deactivates_and_reactivates_staff(self):
        login = self.client.post('/api/auth/login/', {'email': self.nurse.email, 'password': TEST_PASSWORD}).data

        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/staff/{self.nurse.id}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])

        # Their existing tokens stop working immediately
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
        self.assertEqual(self.client.get('/api/auth/me/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials()
        refresh = self.client.post('/api/auth/token/refresh/', {'refresh': login['refresh']})
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.admin)
        self.assertTrue(self.client.post(f'/api/staff/{self.nurse.id}/activate/').data['is_active'])

    def test_only_admins_deactivate_and_never_themselves(self):
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.client.post(f'/api/staff/{self.nurse.id}/deactivate/').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'/api/staff/{self.admin.id}/deactivate/').status_code, 403)

    def test_inactive_doctor_cannot_be_assigned_visits(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f'/api/staff/{self.doctor.id}/deactivate/')
        response = self.client.post(
            '/api/visits/',
            {
                'patient': make_user(Role.PATIENT).patientprofile.id,
                'assigned_doctor': self.doctor.doctorprofile.id,
                'reason_for_visit': 'Fever',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('assigned_doctor', response.data)

    def test_admin_manages_departments(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post('/api/departments/', {'name': 'Emergency'}).status_code, 201)
        self.client.force_authenticate(self.nurse)
        self.assertEqual(self.client.post('/api/departments/', {'name': 'X'}).status_code, 403)
        names = [d['name'] for d in self.client.get('/api/departments/').data['results']]
        self.assertEqual(names, ['Emergency', 'Paediatrics'])
