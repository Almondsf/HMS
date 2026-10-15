import csv
import io
import json
import os
import tempfile
import zipfile
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status

from audit.models import AuditEvent
from authentication.permissions import Role
from helpers.testing import TEST_PASSWORD, TenantAPITestCase, make_user
from subscriptions import services as subscriptions
from subscriptions.models import Subscription

from .export import _cell

EXPORT = '/api/v1/hospital/export/'


def read_zip(content):
    archive = zipfile.ZipFile(io.BytesIO(content))

    def rows(name):
        return list(csv.DictReader(io.TextIOWrapper(archive.open(name), encoding='utf-8-sig')))

    return archive, rows


class ExportTests(TenantAPITestCase):
    def setUp(self):
        self.admin = make_user(Role.ADMIN)
        self.client.force_authenticate(self.admin)
        self.patient = make_user(Role.PATIENT)
        self.patient.phone_number = '+2348031234567'
        self.patient.save()

    def download(self, password=TEST_PASSWORD):
        response = self.client.post(EXPORT, {'password': password})
        content = b''.join(response.streaming_content) if response.status_code == 200 else b''
        return response, content

    def test_admin_downloads_every_record_without_passwords(self):
        response, content = self.download()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment; filename="test_hospital-records-', response['Content-Disposition'])

        archive, rows = read_zip(content)
        users = rows('authentication_user.csv')
        self.assertNotIn('password', users[0])
        patient = next(user for user in users if user['email'] == self.patient.email)
        self.assertEqual(patient['phone_number'], '+2348031234567')  # phone numbers are not mangled
        self.assertEqual(rows('profiles_patientprofile.csv')[0]['user_id'], str(self.patient.pk))

        manifest = json.loads(archive.read('manifest.json'))
        self.assertEqual(manifest['files']['profiles_patientprofile.csv'], 1)
        self.assertIn('README.txt', archive.namelist())
        self.assertTrue(AuditEvent.objects.filter(action='data.exported').exists())

    def test_wrong_password_is_refused_and_logged(self):
        response, _ = self.download(password='wrong-password')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        self.assertTrue(AuditEvent.objects.filter(action='data.export_refused').exists())

    def test_only_admins_can_export(self):
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        self.assertEqual(self.client.post(EXPORT, {'password': TEST_PASSWORD}).status_code, status.HTTP_403_FORBIDDEN)

    def test_a_lapsed_hospital_can_still_take_its_data(self):
        subscriptions.start_trial(self.tenant)
        Subscription.objects.filter(hospital=self.tenant).update(current_period_end=timezone.now() - timedelta(days=60))
        self.assertEqual(self.client.patch('/api/v1/hospital/', {'phone': '1'}).status_code, 402)  # read-only
        response, _ = self.download()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_platform_command_exports_a_hospital(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'export.zip')
            with schema_context('public'):
                call_command('export_hospital', schema=self.tenant.schema_name, output=path, stdout=StringIO())
            with open(path, 'rb') as file:
                _, rows = read_zip(file.read())
        self.assertEqual(len(rows('profiles_patientprofile.csv')), 1)


class FormulaEscapingTests(TenantAPITestCase):
    def test_text_that_would_run_as_a_formula_is_neutralised(self):
        self.assertEqual(_cell('=HYPERLINK("http://evil")'), '\'=HYPERLINK("http://evil")')
        self.assertEqual(_cell('@SUM(A1)'), "'@SUM(A1)")
        self.assertEqual(_cell('-2+3'), "'-2+3")
        self.assertEqual(_cell('+234 803 123 4567'), '+234 803 123 4567')
        self.assertEqual(_cell('-12.50'), '-12.50')
        self.assertEqual(_cell('Paracetamol'), 'Paracetamol')
        self.assertEqual(_cell(None), '')
