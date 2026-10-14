from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from authentication.models import User
from billing.models import Invoice, ServiceItem
from clinical.models import Diagnosis, Visit
from helpers.testing import TenantAPITestCase, make_consultation, make_user
from pharmacy.models import Drug

Role = User.UserType


class ReportTests(TenantAPITestCase):
    def setUp(self):
        self.admin = make_user(Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def report(self, name, **params):
        return self.client.get(f'/api/v1/reports/{name}/', params)

    def test_clinical_report(self):
        consultation = make_consultation()
        Diagnosis.objects.create(consultation=consultation, code_id='B54', description='Unspecified malaria')
        now = timezone.now()
        Visit.objects.filter(pk=consultation.visit_id).update(
            status=Visit.Status.COMPLETED,
            visit_date=now - timedelta(minutes=50),
            started_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=10),
        )

        data = self.report('clinical').data
        self.assertEqual(data['visits']['total'], 1)
        self.assertEqual(data['visits']['by_status'], {'completed': 1})
        self.assertEqual(data['visits']['average_wait_minutes'], 20.0)
        self.assertEqual(data['visits']['average_consultation_minutes'], 20.0)
        self.assertEqual(data['top_diagnoses'], [{'code': 'B54', 'title': 'Unspecified malaria', 'count': 1}])
        self.assertGreaterEqual(data['new_patients'], 1)

    def test_financial_report(self):
        ServiceItem.objects.create(
            code='CONSULT', name='Consultation', category='consultation', price='5000',
            charge_on=ServiceItem.ChargeOn.CONSULTATION_RECORDED,
        )  # fmt: skip
        consultation = make_consultation()
        doctor = consultation.visit.assigned_doctor.user
        self.client.force_authenticate(doctor)
        self.client.post('/api/v1/consultations/', {'visit': consultation.visit_id})

        cashier = make_user(Role.CASHIER)
        self.client.force_authenticate(cashier)
        invoice = Invoice.objects.get()
        self.client.post(f'/api/v1/billing/invoices/{invoice.id}/issue/')
        self.client.post('/api/v1/billing/payments/', {'invoice': invoice.id, 'amount': '2000', 'method': 'cash'})

        data = self.report('financial').data
        self.assertEqual(data['collected']['total'], Decimal('2000.00'))
        self.assertEqual(data['collected']['by_method'], {'cash': Decimal('2000.00')})
        self.assertEqual(data['charged']['by_category'], {'consultation': Decimal('5000.00')})
        self.assertEqual(data['receivables']['patients'], Decimal('3000.00'))
        self.assertEqual(data['receivables']['aging_days']['0-30'], Decimal('3000.00'))

    def test_pharmacy_report(self):
        Drug.objects.create(name='Insulin', quantity_in_stock=2, reorder_level=5, unit_price='4000')
        Drug.objects.create(name='Paracetamol', quantity_in_stock=100, reorder_level=10)
        data = self.report('pharmacy').data
        self.assertEqual([d['name'] for d in data['low_stock']], ['Insulin'])
        self.assertEqual(data['stock_value'], Decimal('8000.00'))
        self.assertEqual(data['drugs_without_price'], 1)

    def test_period_validation(self):
        today = timezone.localdate()
        self.assertEqual(self.report('clinical', date_from='2026-13-01').status_code, status.HTTP_400_BAD_REQUEST)
        backwards = self.report(
            'clinical', date_from=today.isoformat(), date_to=(today - timedelta(days=1)).isoformat()
        )
        self.assertEqual(backwards.status_code, status.HTTP_400_BAD_REQUEST)
        too_long = self.report('clinical', date_from=(today - timedelta(days=400)).isoformat())
        self.assertEqual(too_long.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.report('lab').status_code, status.HTTP_200_OK)

    def test_access(self):
        self.client.force_authenticate(make_user(Role.CASHIER))
        self.assertEqual(self.report('financial').status_code, status.HTTP_200_OK)
        self.assertEqual(self.report('clinical').status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(make_user(Role.DOCTOR))
        self.assertEqual(self.report('financial').status_code, status.HTTP_403_FORBIDDEN)
