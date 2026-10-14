from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django_tenants.utils import schema_context, schema_exists, tenant_context
from rest_framework import status

from audit.models import AuditEvent
from authentication.models import User
from clinical.models import Visit
from helpers.testing import TEST_PASSWORD, SchemaRestoringAPIClient, TenantAPITestCase, make_consultation, make_user
from lab.models import LabTest
from tenants.models import Domain, Hospital
from tenants.services import copy_hospital_data, provision_hospital

Role = User.UserType

OTHER_DOMAIN = 'other-hospital.localhost'


def client_for(host):
    return SchemaRestoringAPIClient(HTTP_HOST=host)


class TwoHospitalsTestCase(TenantAPITestCase):
    '''The standard test hospital plus a second one at OTHER_DOMAIN.'''

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with schema_context('public'):
            cls.other = Hospital(schema_name='other_hospital', name='Other Hospital')
            cls.other.save(verbosity=0)
            Domain.objects.create(domain=OTHER_DOMAIN, tenant=cls.other, is_primary=True)
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.other.delete(force_drop=True)
        super().tearDownClass()


class IsolationTests(TwoHospitalsTestCase):
    def login(self, client, user):
        return client.post('/api/v1/auth/login/', {'email': user.email, 'password': TEST_PASSWORD}).data

    def test_records_are_invisible_to_other_hospitals(self):
        make_consultation()
        self.assertEqual(Visit.objects.count(), 1)

        with tenant_context(self.other):
            self.assertEqual(Visit.objects.count(), 0)
            other_admin = make_user(Role.ADMIN)
        other = client_for(OTHER_DOMAIN)
        other.force_authenticate(other_admin)
        self.assertEqual(other.get('/api/v1/visits/').data['count'], 0)

    def test_token_is_rejected_at_another_hospital_even_for_same_user_id(self):
        doctor = make_user(Role.DOCTOR)
        tokens = self.login(self.client, doctor)

        # Plant a different person with the same user id at the other hospital
        with tenant_context(self.other):
            stranger = make_user(Role.ADMIN)
            User.objects.filter(pk=stranger.pk).update(id=doctor.id)
            self.assertEqual(User.objects.get(id=doctor.id).email, stranger.email)

        other = client_for(OTHER_DOMAIN)
        other.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(other.get('/api/v1/auth/me/').status_code, status.HTTP_401_UNAUTHORIZED)
        refresh = other.post('/api/v1/auth/token/refresh/', {'refresh': tokens['refresh']})
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

        # Still valid where it was issued
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').data['email'], doctor.email)

    def test_suspended_hospital_is_refused(self):
        with schema_context('public'):
            Hospital.objects.filter(pk=self.other.pk).update(is_active=False)
        response = client_for(OTHER_DOMAIN).get('/api/v1/visits/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('suspended', response.json()['detail'])

    def test_unknown_address_is_not_found(self):
        response = client_for('nowhere.localhost').get('/api/v1/visits/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_health_check_answers_on_any_host(self):
        for host in ['nowhere.localhost', 'internal-probe', OTHER_DOMAIN]:
            with self.subTest(host=host):
                response = client_for(host).get('/api/health/')
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()['database'], 'up')


class PlatformSiteTests(TenantAPITestCase):
    def setUp(self):
        with schema_context('public'):
            call_command('setup_platform', 'platform.localhost', stdout=StringIO())
            self.operator = User.objects.create_user(
                email='ops@example.com', password=TEST_PASSWORD, first_name='Ops', last_name='Team',
                user_type=Role.ADMIN, is_superuser=True,
            )  # fmt: skip
        connection.set_tenant(self.tenant)
        self.platform = client_for('platform.localhost')

    def test_platform_has_no_hospital_endpoints(self):
        self.platform.force_authenticate(self.operator)
        self.assertEqual(self.platform.get('/api/v1/visits/').status_code, status.HTTP_404_NOT_FOUND)

    def test_platform_token_is_not_valid_at_hospitals(self):
        tokens = self.platform.post('/api/v1/auth/login/', {'email': 'ops@example.com', 'password': TEST_PASSWORD}).data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, status.HTTP_401_UNAUTHORIZED)


class ProvisioningTests(TestCase):
    '''Runs in one transaction per test: created schemas are rolled back too.'''

    def provision(self, **overrides):
        options = {
            'name': "St Luke's Hospital", 'schema_name': 'stlukes', 'admin_email': 'admin@stlukes.example',
            'admin_password': 'Adm1n-pass-strong', 'admin_first_name': 'Ada', 'admin_last_name': 'Admin',
            **overrides,
        }  # fmt: skip
        return provision_hospital(**options)

    def test_provisioned_hospital_is_ready_to_use(self):
        hospital, admin = self.provision()

        self.assertEqual(hospital.get_primary_domain().domain, 'stlukes.localhost')
        self.assertTrue(schema_exists('stlukes'))
        self.assertTrue(AuditEvent.objects.filter(action='platform.hospital_provisioned').exists())

        client = client_for('stlukes.localhost')
        response = client.post('/api/v1/auth/login/', {'email': admin.email, 'password': 'Adm1n-pass-strong'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['user_type'], 'admin')
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(client.get('/api/v1/visits/').status_code, status.HTTP_200_OK)

    def test_invalid_requests_create_nothing(self):
        for overrides in [{'schema_name': 'Bad Name!'}, {'schema_name': 'public'}, {'admin_password': '123'}]:
            with self.subTest(**overrides), self.assertRaises(ValidationError):
                self.provision(**overrides)
        self.assertFalse(schema_exists('stlukes'))
        self.assertFalse(Hospital.objects.filter(schema_name='stlukes').exists())

    def test_duplicate_address_is_refused(self):
        self.provision()
        with self.assertRaises(ValidationError):
            self.provision(schema_name='stlukes2', domain='stlukes.localhost')


class CopyHospitalDataTests(TenantAPITestCase):
    def test_existing_data_is_copied_into_a_new_hospital(self):
        consultation = make_consultation()
        doctor_email = consultation.visit.assigned_doctor.user.email

        with schema_context('public'):
            target, _ = provision_hospital(
                name='Migrated', schema_name='migrated', admin_email='a@example.com',
                admin_password='Adm1n-pass-strong', admin_first_name='A', admin_last_name='B',
            )  # fmt: skip

            with self.assertRaises(ValidationError):  # target already has its admin user
                copy_hospital_data(source_schema=self.tenant.schema_name, target_schema='migrated')
            copied = copy_hospital_data(source_schema=self.tenant.schema_name, target_schema='migrated', force=True)
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')  # verify every foreign key now

        self.assertEqual(copied['clinical_visit'], 1)
        with tenant_context(target):
            visit = Visit.objects.get()
            self.assertEqual(visit.assigned_doctor.user.email, doctor_email)
            # Id sequences continue after the copied rows
            newer = make_consultation()
            self.assertGreater(newer.visit_id, visit.id)


class PlatformHospitalApiTests(PlatformSiteTests):
    def test_operator_provisions_a_hospital(self):
        self.platform.force_authenticate(self.operator)
        response = self.platform.post('/api/v1/platform/hospitals/', {
            'name': 'Mercy Clinic', 'schema_name': 'mercy', 'plan': 'pro',
            'admin_email': 'admin@mercy.example', 'admin_first_name': 'Mary', 'admin_last_name': 'Admin',
        })  # fmt: skip

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['domains'], ['mercy.localhost'])
        self.assertEqual(response.data['features'], ['billing', 'clinical', 'lab', 'pharmacy'])
        password = response.data['admin']['temporary_password']

        login = client_for('mercy.localhost').post(
            '/api/v1/auth/login/', {'email': 'admin@mercy.example', 'password': password}
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_operator_suspends_a_hospital(self):
        self.platform.force_authenticate(self.operator)
        response = self.platform.patch(f'/api/v1/platform/hospitals/{self.tenant.pk}/', {'is_active': False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/v1/visits/').status_code, status.HTTP_403_FORBIDDEN)

    def test_list_excludes_the_platform_itself(self):
        self.platform.force_authenticate(self.operator)
        schemas = [h['schema_name'] for h in self.platform.get('/api/v1/platform/hospitals/').data['results']]
        self.assertIn(self.tenant.schema_name, schemas)
        self.assertNotIn('public', schemas)

    def test_only_platform_superusers_manage_hospitals(self):
        with schema_context('public'):
            staff = make_user(Role.ADMIN)  # a platform account without superuser rights
        self.platform.force_authenticate(staff)
        self.assertEqual(self.platform.get('/api/v1/platform/hospitals/').status_code, status.HTTP_403_FORBIDDEN)

        # Hospital admins don't even see the platform API on their own site
        self.client.force_authenticate(make_user(Role.ADMIN))
        self.assertEqual(self.client.get('/api/v1/platform/hospitals/').status_code, status.HTTP_404_NOT_FOUND)


class HospitalSettingsTests(TenantAPITestCase):
    def test_staff_read_and_admins_edit_settings(self):
        self.client.force_authenticate(make_user(Role.DOCTOR))
        response = self.client.get('/api/v1/hospital/')
        self.assertEqual(response.data['name'], 'Test Hospital')
        self.assertEqual(response.data['domain'], 'test-hospital.localhost')
        self.assertEqual(self.client.patch('/api/v1/hospital/', {'phone': '0800'}).status_code, 403)

        self.client.force_authenticate(make_user(Role.ADMIN))
        response = self.client.patch('/api/v1/hospital/', {'phone': '+2348000000000', 'mrn_prefix': 'SLH'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['mrn_prefix'], 'SLH')
        self.assertTrue(AuditEvent.objects.filter(resource_type='tenants.hospital', action='update').exists())

    def test_admins_cannot_change_their_own_plan(self):
        self.client.force_authenticate(make_user(Role.ADMIN))
        self.client.patch('/api/v1/hospital/', {'plan': 'enterprise', 'name': 'Renamed'})
        with schema_context('public'):
            hospital = Hospital.objects.get(pk=self.tenant.pk)
        self.assertEqual((hospital.plan, hospital.name), ('enterprise', 'Renamed'))  # test hospital is enterprise

        Hospital.objects.filter(pk=self.tenant.pk).update(plan='basic')
        self.client.patch('/api/v1/hospital/', {'plan': 'enterprise'})
        self.assertEqual(Hospital.objects.get(pk=self.tenant.pk).plan, 'basic')

    def test_invalid_settings_are_rejected(self):
        self.client.force_authenticate(make_user(Role.ADMIN))
        for field, value in [('timezone', 'Mars/Olympus'), ('currency', 'naira'), ('mrn_prefix', 'bad prefix')]:
            with self.subTest(field=field):
                self.assertEqual(self.client.patch('/api/v1/hospital/', {field: value}).status_code, 400)

    def test_times_are_shown_in_the_hospitals_timezone(self):
        Hospital.objects.filter(pk=self.tenant.pk).update(timezone='Africa/Nairobi')
        consultation = make_consultation()
        self.client.force_authenticate(consultation.visit.assigned_doctor.user)
        visit = self.client.get(f'/api/v1/visits/{consultation.visit_id}/').data
        self.assertTrue(visit['visit_date'].endswith('+03:00'), visit['visit_date'])


class PlanFeatureTests(TenantAPITestCase):
    def setUp(self):
        Hospital.objects.filter(pk=self.tenant.pk).update(plan=Hospital.Plan.BASIC)

    def test_basic_plan_has_no_lab(self):
        self.client.force_authenticate(make_user(Role.LAB_TECHNICIAN))
        response = self.client.get('/api/v1/lab/tests/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Laboratory', str(response.data['detail']))

        self.client.force_authenticate(make_user(Role.PHARMACIST))
        self.assertEqual(self.client.get('/api/v1/pharmacy/drugs/').status_code, status.HTTP_200_OK)

    def test_consultation_cannot_order_lab_tests_without_lab(self):
        consultation = make_consultation()
        test = LabTest.objects.create(name='FBC', cost=100)
        self.client.force_authenticate(consultation.visit.assigned_doctor.user)
        response = self.client.post(
            '/api/v1/consultations/', {'visit': consultation.visit_id, 'lab_tests': [test.id]}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lab_tests', response.data)
