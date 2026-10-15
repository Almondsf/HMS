import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework import status

from audit.models import AuditEvent
from authentication.permissions import Role
from helpers.testing import TenantAPITestCase, make_user

from .models import PatientProfile

IMPORT = '/api/v1/patients/import/'


def csv_file(text, name='patients.csv'):
    return SimpleUploadedFile(name, text.encode('utf-8'), content_type='text/csv')


GOOD = (
    'First name,Surname,Sex,DOB,Phone,Email,Blood group,Genotype,Card number\n'
    'Ada,Obi,F,31/12/1990,0803 123 4567,ada@example.com,o+,AS,OLD-001\n'
    'Musa,Bello,male,1985-06-01,08051112222,,,,\n'
)


class PatientImportTests(TenantAPITestCase):
    def setUp(self):
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))

    def upload(self, file, **options):
        return self.client.post(IMPORT, {'file': file, **options}, format='multipart')

    def test_template_lists_the_columns(self):
        response = self.client.get('/api/v1/patients/import-template/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('First name,Last name,Gender,Date of birth', response.content.decode('utf-8-sig'))

    def test_preview_saves_nothing(self):
        data = self.upload(csv_file(GOOD)).data
        self.assertEqual((data['total_rows'], data['valid_rows'], data['imported']), (2, 2, 0))
        self.assertEqual(data['preview'][0]['name'], 'Ada Obi')
        self.assertEqual(data['preview'][1]['mrn'], '(new number)')
        self.assertFalse(PatientProfile.objects.exists())

    def test_import_saves_patients_with_cleaned_values(self):
        data = self.upload(csv_file(GOOD), dry_run='false').data
        self.assertEqual(data['imported'], 2)
        ada = PatientProfile.objects.select_related('user').get(mrn='OLD-001')
        self.assertEqual(ada.user.gender, 'female')
        self.assertEqual(ada.user.date_of_birth, date(1990, 12, 31))
        self.assertEqual(ada.user.phone_number, '08031234567')
        self.assertEqual((ada.blood_group, ada.genotype), ('O+', 'AS'))
        self.assertTrue(PatientProfile.objects.filter(user__last_name='Bello').exclude(mrn='').exists())
        self.assertTrue(AuditEvent.objects.filter(action='patients.imported').exists())

    def test_problems_are_listed_by_row_and_block_the_import(self):
        text = (
            'First name,Last name,Date of birth,Gender,Email\n'
            'Ada,Obi,1990-13-45,F,a@example.com\n'  # bad date
            'Ola,Ade,,unknown,b@example.com\n'  # bad gender
            ',Nobody,,,\n'  # no first name
            'Ifeoma,Eze,,,a@example.com\n'  # same email as row 2
            'Good,Row,,,\n'
        )
        data = self.upload(csv_file(text), dry_run='false').data
        problems = {(error['row'], error['column']) for error in data['errors']}
        self.assertEqual(problems, {(2, 'Date of birth'), (3, 'Gender'), (4, 'First name'), (5, 'Email')})
        self.assertEqual((data['valid_rows'], data['imported']), (1, 0))
        self.assertFalse(PatientProfile.objects.exists())

    def test_skip_invalid_imports_only_good_rows(self):
        text = 'First name,Last name,Gender\nAda,Obi,F\nBad,Row,maybe\n'
        data = self.upload(csv_file(text), dry_run='false', skip_invalid='true').data
        self.assertEqual(data['imported'], 1)
        self.assertEqual(PatientProfile.objects.count(), 1)

    def test_existing_patients_are_flagged_as_possible_duplicates(self):
        self.upload(csv_file(GOOD), dry_run='false')
        data = self.upload(csv_file(GOOD.replace('OLD-001', 'OLD-999').replace('ada@', 'ada2@'))).data
        self.assertIn('already registered', data['errors'][0]['message'])

    def test_excel_files_and_lost_leading_zeros(self):
        book = Workbook()
        sheet = book.active
        sheet.append(['First Name', 'Last Name', 'Date of Birth', 'Mobile'])
        sheet.append(['Ada', 'Obi', date(1990, 12, 31), 8031234567])  # Excel turned 0803... into a number
        stream = io.BytesIO()
        book.save(stream)
        upload = SimpleUploadedFile('patients.xlsx', stream.getvalue())
        data = self.upload(upload, dry_run='false').data
        self.assertEqual(data['imported'], 1, data)
        patient = PatientProfile.objects.select_related('user').get()
        self.assertEqual(patient.user.phone_number, '08031234567')
        self.assertEqual(patient.user.date_of_birth, date(1990, 12, 31))

    def test_unusable_files_are_explained(self):
        cases = {
            'no names': csv_file('Phone,Email\n0803,a@b.com\n'),
            'wrong type': SimpleUploadedFile('patients.pdf', b'%PDF'),
            'empty': csv_file(''),
        }
        for case, upload in cases.items():
            with self.subTest(case):
                response = self.upload(upload)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('file', response.data)

    def test_only_front_desk_and_admins_import(self):
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.upload(csv_file(GOOD)).status_code, status.HTTP_403_FORBIDDEN)
