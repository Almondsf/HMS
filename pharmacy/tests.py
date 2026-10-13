from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from helpers.testing import make_user

Role = User.UserType


class DepartmentAccessTests(APITestCase):
    '''Role rules for the pharmacy and lab endpoints.'''

    def status_for(self, role, method, url, data=None):
        self.client.force_authenticate(make_user(role))
        return getattr(self.client, method)(url, data, format='json').status_code

    def test_patient_cannot_read_lab_or_pharmacy_data(self):
        for url in ['/api/lab/test-results/', '/api/lab/test-orders/', '/api/pharmacy/drugs/',
                    '/api/pharmacy/dispense-transactions/']:
            with self.subTest(url=url):
                self.assertEqual(self.status_for(Role.PATIENT, 'get', url), status.HTTP_403_FORBIDDEN)

    def test_drug_stock_is_managed_by_pharmacy(self):
        drug = {'name': 'Paracetamol', 'unit': 'tablet', 'quantity_in_stock': 100}
        self.assertEqual(self.status_for(Role.DOCTOR, 'get', '/api/pharmacy/drugs/'), status.HTTP_200_OK)
        self.assertEqual(self.status_for(Role.DOCTOR, 'post', '/api/pharmacy/drugs/', drug),
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.status_for(Role.PHARMACIST, 'post', '/api/pharmacy/drugs/', drug),
                         status.HTTP_201_CREATED)

    def test_only_lab_tech_records_results(self):
        self.assertEqual(self.status_for(Role.DOCTOR, 'post', '/api/lab/test-results/', {}),
                         status.HTTP_403_FORBIDDEN)

    def test_dispense_records_cannot_be_deleted(self):
        self.assertEqual(self.status_for(Role.PHARMACIST, 'delete', '/api/pharmacy/dispense-transactions/1/'),
                         status.HTTP_405_METHOD_NOT_ALLOWED)
