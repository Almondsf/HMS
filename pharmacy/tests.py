from rest_framework import status

from authentication.models import User
from clinical.models import Prescription
from helpers.testing import TenantAPITestCase, make_consultation, make_user
from pharmacy.models import DispenseTransaction, Drug

Role = User.UserType


class DepartmentAccessTests(TenantAPITestCase):
    '''Role rules for the pharmacy and lab endpoints.'''

    def status_for(self, role, method, url, data=None):
        self.client.force_authenticate(make_user(role))
        return getattr(self.client, method)(url, data, format='json').status_code

    def test_patient_cannot_read_lab_or_pharmacy_data(self):
        for url in [
            '/api/lab/test-results/',
            '/api/lab/test-orders/',
            '/api/pharmacy/drugs/',
            '/api/pharmacy/dispense-transactions/',
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.status_for(Role.PATIENT, 'get', url), status.HTTP_403_FORBIDDEN)

    def test_drug_stock_is_managed_by_pharmacy(self):
        drug = {'name': 'Paracetamol', 'unit': 'tablet', 'quantity_in_stock': 100}
        self.assertEqual(self.status_for(Role.DOCTOR, 'get', '/api/pharmacy/drugs/'), status.HTTP_200_OK)
        self.assertEqual(self.status_for(Role.DOCTOR, 'post', '/api/pharmacy/drugs/', drug), status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.status_for(Role.PHARMACIST, 'post', '/api/pharmacy/drugs/', drug), status.HTTP_201_CREATED
        )

    def test_only_lab_tech_records_results(self):
        self.assertEqual(self.status_for(Role.DOCTOR, 'post', '/api/lab/test-results/', {}), status.HTTP_403_FORBIDDEN)

    def test_dispense_records_cannot_be_deleted(self):
        self.assertEqual(
            self.status_for(Role.PHARMACIST, 'delete', '/api/pharmacy/dispense-transactions/1/'),
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class DispenseTests(TenantAPITestCase):
    def setUp(self):
        self.pharmacist = make_user(Role.PHARMACIST)
        self.drug = Drug.objects.create(name='Amoxicillin', unit='capsule', quantity_in_stock=30, reorder_level=10)
        self.prescription = self.prescribe(self.drug, quantity=21)
        self.client.force_authenticate(self.pharmacist)

    def prescribe(self, drug, quantity=None, consultation=None):
        return Prescription.objects.create(
            consultation=consultation or make_consultation(),
            drug=drug,
            medication_name=drug.name,
            dosage='500mg',
            frequency='TDS',
            duration='7 days',
            quantity=quantity,
        )

    def dispense(self, *items):
        return self.client.post(
            '/api/pharmacy/dispense-transactions/',
            {'items': [{'prescription': p.id, 'drug': d.id, 'quantity_dispensed': q} for p, d, q in items]},
            format='json',
        )

    def test_dispense_deducts_stock(self):
        response = self.dispense((self.prescription, self.drug, 21))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.quantity_in_stock, 9)
        self.assertTrue(self.drug.is_low_stock)
        self.assertEqual(response.data['pharmacist_name'], self.pharmacist.get_full_name())

    def test_cannot_exceed_stock_across_split_lines(self):
        # Each line alone fits in stock; together they don't
        other = self.prescribe(self.drug, consultation=self.prescription.consultation)
        response = self.dispense((self.prescription, self.drug, 20), (other, self.drug, 20))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.quantity_in_stock, 30)
        self.assertFalse(DispenseTransaction.objects.exists())

    def test_cannot_exceed_prescribed_quantity(self):
        self.assertEqual(self.dispense((self.prescription, self.drug, 15)).status_code, 201)
        response = self.dispense((self.prescription, self.drug, 10))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('6 unit(s) left', str(response.data))

    def test_must_dispense_the_prescribed_drug(self):
        other_drug = Drug.objects.create(name='Ciprofloxacin', quantity_in_stock=100)
        response = self.dispense((self.prescription, other_drug, 5))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_one_patient_per_dispense(self):
        other_patients = self.prescribe(self.drug)
        response = self.dispense((self.prescription, self.drug, 1), (other_patients, self.drug, 1))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_superuser_without_pharmacist_profile_gets_clear_error(self):
        admin = User.objects.create_superuser(
            email='root@example.com', first_name='Root', last_name='User', password='Str0ng-pass!'
        )
        self.client.force_authenticate(admin)
        response = self.dispense((self.prescription, self.drug, 1))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_prescribed_drug_cannot_be_deleted(self):
        self.client.force_authenticate(make_user(Role.ADMIN))
        response = self.client.delete(f'/api/pharmacy/drugs/{self.drug.id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
