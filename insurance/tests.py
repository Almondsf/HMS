from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from authentication.models import User
from billing.models import ServiceItem
from helpers.testing import TenantAPITestCase, make_consultation, make_user
from insurance.models import Coverage, InsuranceProvider
from tenants.models import Hospital
from terminology.models import Icd10Code

Role = User.UserType


class ClaimTestCase(TenantAPITestCase):
    '''An issued 10,000 invoice for a patient covered 80% by an HMO.'''

    def setUp(self):
        self.cashier = make_user(Role.CASHIER)
        ServiceItem.objects.create(
            code='CONSULT', name='Specialist consultation', category='consultation', price='10000',
            charge_on=ServiceItem.ChargeOn.CONSULTATION_RECORDED,
        )  # fmt: skip
        self.provider = InsuranceProvider.objects.create(
            name='Hygeia HMO', code='HYG', default_coverage_percent=Decimal('80')
        )
        consultation = make_consultation()
        self.patient = consultation.visit.patient
        self.coverage = Coverage.objects.create(
            patient=self.patient, provider=self.provider, member_number='HYG-123',
            valid_from=date.today() - timedelta(days=30),
        )  # fmt: skip

        # Recording a consultation through the API bills the consultation fee
        self.client.force_authenticate(consultation.visit.assigned_doctor.user)
        self.client.post('/api/v1/consultations/', {'visit': consultation.visit_id, 'assessment': 'Malaria'})
        self.client.post('/api/v1/diagnoses/', {
            'consultation': consultation.visit.consultations.latest('id').id, 'code': 'B54', 'certainty': 'confirmed',
        })  # fmt: skip

        self.client.force_authenticate(self.cashier)
        [invoice] = self.client.get('/api/v1/billing/invoices/', {'visit': consultation.visit_id}).data['results']
        self.invoice_url = f"/api/v1/billing/invoices/{invoice['id']}/"
        self.client.post(f'{self.invoice_url}issue/')
        self.invoice_id = invoice['id']

    def claim(self, **extra):
        return self.client.post(
            '/api/v1/insurance/claims/', {'invoice': self.invoice_id, 'coverage': self.coverage.id, **extra}
        )

    def invoice(self):
        return self.client.get(self.invoice_url).data


class ClaimFlowTests(ClaimTestCase):
    def test_full_claim_lifecycle(self):
        claim = self.claim().data
        self.assertEqual((claim['status'], claim['claimed_amount']), ('draft', '8000.00'))
        self.assertRegex(claim['number'], r'^CLM-\d{6}$')
        invoice = self.invoice()
        self.assertEqual((invoice['pending_insurance'], invoice['patient_due']), ('8000.00', '2000.00'))

        # The patient pays their 20% co-payment, and no more
        self.assertEqual(self.client.post('/api/v1/billing/payments/', {
            'invoice': self.invoice_id, 'amount': '2000.01', 'method': 'cash',
        }).status_code, status.HTTP_400_BAD_REQUEST)  # fmt: skip
        self.client.post('/api/v1/billing/payments/', {'invoice': self.invoice_id, 'amount': '2000', 'method': 'cash'})

        url = f"/api/v1/insurance/claims/{claim['id']}/"
        self.assertEqual(self.client.post(f'{url}submit/').data['status'], 'submitted')
        self.assertEqual(self.client.post(f'{url}respond/', {'approved_amount': '8000'}).data['status'], 'approved')
        paid = self.client.post(f'{url}pay/', {'amount': '8000', 'reference': 'HYG-REMIT-77'})
        self.assertEqual(paid.data['status'], 'paid', paid.data)

        invoice = self.invoice()
        self.assertEqual((invoice['status'], invoice['balance']), ('paid', '0.00'))
        self.assertIn('insurance', [p['method'] for p in invoice['payments']])

    def test_rejection_returns_the_amount_to_the_patient(self):
        claim = self.claim().data
        url = f"/api/v1/insurance/claims/{claim['id']}/"
        self.client.post(f'{url}submit/')
        self.client.post(f'{url}respond/', {'rejection_reason': 'Not covered under plan'})
        self.assertEqual(self.invoice()['patient_due'], '10000.00')

        # A new claim can be raised after a rejection (e.g. with corrected details)
        self.assertEqual(self.claim().status_code, status.HTTP_201_CREATED)

    def test_partial_approval_and_short_payment_fall_back_to_the_patient(self):
        claim = self.claim().data
        url = f"/api/v1/insurance/claims/{claim['id']}/"
        self.client.post(f'{url}submit/')
        self.client.post(f'{url}respond/', {'approved_amount': '6000'})
        self.assertEqual(self.invoice()['patient_due'], '4000.00')

        self.client.post(f'{url}pay/', {'amount': '5500'})
        self.assertEqual(self.invoice()['patient_due'], '4500.00')  # 500 shortfall now with the patient

    def test_claim_document_has_icd_codes_and_items(self):
        claim = self.claim().data
        document = self.client.get(f"/api/v1/insurance/claims/{claim['id']}/document/").data
        self.assertEqual(document['member']['member_number'], 'HYG-123')
        self.assertEqual(document['member']['mrn'], self.patient.mrn)
        self.assertEqual([d['code'] for d in document['diagnoses']], ['B54'])
        self.assertEqual([line['description'] for line in document['lines']], ['Specialist consultation'])
        self.assertEqual(document['claimed_amount'], Decimal('8000.00'))
        self.assertTrue(Icd10Code.objects.filter(code='B54').exists())

    def test_outstanding_by_provider(self):
        self.claim()
        summary = self.client.get('/api/v1/insurance/claims/outstanding/').data
        self.assertEqual(summary['Hygeia HMO']['total'], Decimal('8000.00'))
        self.assertEqual(summary['Hygeia HMO']['by_status']['draft']['count'], 1)


class ClaimRulesTests(ClaimTestCase):
    def test_one_open_claim_per_invoice(self):
        self.claim()
        self.assertEqual(self.claim().status_code, status.HTTP_400_BAD_REQUEST)

    def test_cover_must_be_valid_on_the_date_of_service(self):
        Coverage.objects.filter(pk=self.coverage.pk).update(valid_to=timezone.localdate() - timedelta(days=1))
        response = self.claim()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('coverage', response.data)

    def test_authorisation_code_when_the_provider_requires_it(self):
        InsuranceProvider.objects.filter(pk=self.provider.pk).update(requires_authorization=True)
        self.assertEqual(self.claim().status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.claim(authorization_code='PA-5521').status_code, status.HTTP_201_CREATED)

    def test_insurance_payments_only_through_claims(self):
        response = self.client.post(
            '/api/v1/billing/payments/', {'invoice': self.invoice_id, 'amount': '100', 'method': 'insurance'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_insurance_needs_a_pro_plan(self):
        Hospital.objects.filter(pk=self.tenant.pk).update(plan=Hospital.Plan.BASIC)
        self.assertEqual(self.client.get('/api/v1/insurance/claims/').status_code, status.HTTP_403_FORBIDDEN)

    def test_who_handles_claims_and_cover(self):
        self.client.force_authenticate(make_user(Role.RECEPTIONIST))
        self.assertEqual(self.claim().status_code, status.HTTP_403_FORBIDDEN)
        cover = self.client.post('/api/v1/insurance/coverages/', {
            'patient': self.patient.id, 'provider': self.provider.id, 'member_number': 'HYG-999',
            'valid_from': date.today().isoformat(),
        })  # fmt: skip
        self.assertEqual(cover.status_code, status.HTTP_201_CREATED, cover.data)
        self.assertEqual(cover.data['effective_percent'], '80.00')

        self.client.force_authenticate(self.patient.user)
        self.assertEqual(len(self.client.get('/api/v1/insurance/coverages/').data['results']), 2)
