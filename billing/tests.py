from decimal import Decimal
from unittest import mock

from django.db import connection
from django_tenants.utils import schema_context
from rest_framework import status

from audit import events
from audit.models import AuditEvent
from authentication.models import User
from billing.models import Invoice, InvoiceLine, Payment, ServiceItem
from clinical.models import Prescription, Visit
from helpers.testing import TenantAPITestCase, make_consultation, make_user
from lab.models import LabTest
from pharmacy.models import DispenseTransaction, Drug
from tenants import features
from tenants.models import Hospital

Role = User.UserType


class BillingTestCase(TenantAPITestCase):
    def setUp(self):
        self.cashier = make_user(Role.CASHIER)
        self.receptionist = make_user(Role.RECEPTIONIST)
        self.doctor = make_user(Role.DOCTOR)
        self.patient = make_user(Role.PATIENT).patientprofile
        ServiceItem.objects.create(
            code='CARD', name='Hospital card', category='registration', price='1000',
            charge_on=ServiceItem.ChargeOn.VISIT_OPENED,
        )  # fmt: skip
        ServiceItem.objects.create(
            code='CONSULT', name='GP consultation', category='consultation', price='5000',
            charge_on=ServiceItem.ChargeOn.CONSULTATION_RECORDED,
        )  # fmt: skip

    def open_visit(self):
        self.client.force_authenticate(self.receptionist)
        response = self.client.post('/api/v1/visits/', {
            'patient': self.patient.id, 'assigned_doctor': self.doctor.doctorprofile.id, 'reason_for_visit': 'Fever',
        })  # fmt: skip
        return response.data['id']

    def consult(self, visit_id, **extra):
        self.client.force_authenticate(self.doctor)
        return self.client.post('/api/v1/consultations/', {'visit': visit_id, **extra}, format='json')

    def invoice_for(self, visit_id):
        self.client.force_authenticate(self.cashier)
        [invoice] = self.client.get('/api/v1/billing/invoices/', {'visit': visit_id}).data['results']
        return invoice


class AutomaticChargeTests(BillingTestCase):
    def test_visit_consultation_lab_and_pharmacy_are_billed(self):
        LabTest.objects.create(name='Malaria parasite', cost='1500')
        drug = Drug.objects.create(name='Artemether', unit='tablet', quantity_in_stock=50, unit_price='200')
        visit_id = self.open_visit()
        consultation = self.consult(visit_id, lab_tests=[LabTest.objects.get().id], prescriptions=[
            {'drug': drug.id, 'dosage': '80mg', 'frequency': 'BD', 'duration': '3 days', 'quantity': 6},
        ]).data  # fmt: skip

        self.client.force_authenticate(make_user(Role.PHARMACIST))
        self.client.post('/api/v1/pharmacy/dispense-transactions/', {'items': [{
            'prescription': consultation['prescriptions'][0]['id'], 'drug': drug.id, 'quantity_dispensed': 6,
        }]}, format='json')  # fmt: skip

        invoice = self.invoice_for(visit_id)
        lines = {line['description']: line['amount'] for line in invoice['lines']}
        self.assertEqual(lines, {
            'Hospital card': '1000.00', 'GP consultation': '5000.00',
            'Lab: Malaria parasite': '1500.00', 'Artemether (tablet)': '1200.00',
        })  # fmt: skip
        self.assertEqual((invoice['total'], invoice['balance'], invoice['status']), ('8700.00', '8700.00', 'draft'))
        self.assertRegex(invoice['number'], r'^INV-\d{6}$')

    def test_each_source_is_charged_once(self):
        visit_id = self.open_visit()
        events.publish('clinical.visit_opened', resource=Visit.objects.get(pk=visit_id))
        self.assertEqual(len(self.invoice_for(visit_id)['lines']), 1)

    def test_unpriced_drug_is_flagged_not_blocking(self):
        drug = Drug.objects.create(name='Ceftriaxone', unit='vial', quantity_in_stock=10)  # no price yet
        consultation = make_consultation(doctor=self.doctor, patient=self.patient.user)
        prescription = Prescription.objects.create(
            consultation=consultation, drug=drug, medication_name='Ceftriaxone',
            dosage='1g', frequency='OD', duration='1 day', quantity=1,
        )  # fmt: skip
        self.client.force_authenticate(make_user(Role.PHARMACIST))
        dispensed = self.client.post('/api/v1/pharmacy/dispense-transactions/', {
            'items': [{'prescription': prescription.id, 'drug': drug.id, 'quantity_dispensed': 1}]
        }, format='json')  # fmt: skip
        self.assertEqual(dispensed.status_code, status.HTTP_201_CREATED)  # care is never blocked

        invoice = self.invoice_for(consultation.visit_id)
        [line] = invoice['lines']
        self.assertTrue(line['needs_price'])
        issue = self.client.post(f"/api/v1/billing/invoices/{invoice['id']}/issue/")
        self.assertEqual(issue.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Ceftriaxone', str(issue.data))

        priced = self.client.post(
            f"/api/v1/billing/invoices/{invoice['id']}/lines/{line['id']}/price/", {'unit_price': '3500'}
        )
        self.assertEqual(priced.data['total'], '3500.00')
        self.assertEqual(self.client.post(f"/api/v1/billing/invoices/{invoice['id']}/issue/").data['status'], 'issued')

    def test_a_failed_charge_rolls_back_the_clinical_action(self):
        # Never record a service without its charge (or vice versa)
        drug = Drug.objects.create(name='Amoxicillin', quantity_in_stock=10, unit_price='50')
        consultation = make_consultation(doctor=self.doctor, patient=self.patient.user)
        prescription = Prescription.objects.create(
            consultation=consultation, drug=drug, medication_name='Amoxicillin',
            dosage='500mg', frequency='TDS', duration='5 days',
        )  # fmt: skip
        self.client.force_authenticate(make_user(Role.PHARMACIST))
        self.client.raise_request_exception = False
        with mock.patch('billing.services.add_charge', side_effect=RuntimeError('billing down')):
            response = self.client.post('/api/v1/pharmacy/dispense-transactions/', {
                'items': [{'prescription': prescription.id, 'drug': drug.id, 'quantity_dispensed': 5}]
            }, format='json')  # fmt: skip

        self.assertEqual(response.status_code, 500)
        drug.refresh_from_db()
        self.assertEqual(drug.quantity_in_stock, 10)
        self.assertFalse(DispenseTransaction.objects.exists())

    def test_walk_in_lab_patient_gets_their_own_invoice(self):
        test = LabTest.objects.create(name='FBC', cost='3000')
        self.client.force_authenticate(make_user(Role.LAB_TECHNICIAN))
        self.client.post('/api/v1/lab/test-orders/', {'patient': self.patient.id, 'tests': [test.id]}, format='json')
        invoice = Invoice.objects.get(patient=self.patient)
        self.assertIsNone(invoice.visit)
        self.assertEqual(invoice.total, Decimal('3000.00'))

    def test_no_charges_when_billing_is_not_in_the_plan(self):
        features.PLAN_FEATURES['test-no-billing'] = {features.Feature.CLINICAL}
        self.addCleanup(features.PLAN_FEATURES.pop, 'test-no-billing')
        Hospital.objects.filter(pk=self.tenant.pk).update(plan='test-no-billing')
        self.open_visit()
        self.assertFalse(InvoiceLine.objects.exists())


class PaymentTests(BillingTestCase):
    def setUp(self):
        super().setUp()
        self.visit_id = self.open_visit()
        self.consult(self.visit_id)
        self.invoice = self.invoice_for(self.visit_id)  # 6000.00 due
        self.url = f"/api/v1/billing/invoices/{self.invoice['id']}"

    def pay(self, amount, method='cash', **extra):
        return self.client.post('/api/v1/billing/payments/', {
            'invoice': self.invoice['id'], 'amount': amount, 'method': method, **extra,
        })  # fmt: skip

    def test_part_payments_then_paid(self):
        self.client.post(f'{self.url}/issue/')
        first = self.pay('2500', 'transfer', reference='TRF-881')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertRegex(first.data['receipt_number'], r'^RCT-\d{6}$')
        self.assertEqual(self.client.get(f'{self.url}/').data['balance'], '3500.00')

        self.pay('3500')
        invoice = self.client.get(f'{self.url}/').data
        self.assertEqual((invoice['status'], invoice['balance']), ('paid', '0.00'))
        self.assertTrue(AuditEvent.objects.filter(action='billing.invoice_paid').exists())

    def test_cannot_overpay_or_pay_void_invoices(self):
        response = self.pay('6000.01')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount due', str(response.data))
        self.assertEqual(self.pay('-5').status_code, status.HTTP_400_BAD_REQUEST)

    def test_voiding_a_payment_reopens_the_invoice(self):
        self.client.post(f'{self.url}/issue/')
        payment = self.pay('6000').data
        self.assertEqual(
            self.client.post(f"/api/v1/billing/payments/{payment['id']}/void/", {'reason': 'x'}).status_code, 403
        )

        self.client.force_authenticate(make_user(Role.ADMIN))
        voided = self.client.post(f"/api/v1/billing/payments/{payment['id']}/void/", {'reason': 'Duplicate POS'})
        self.assertTrue(voided.data['voided'])
        invoice = self.client.get(f'{self.url}/').data
        self.assertEqual((invoice['status'], invoice['balance']), ('issued', '6000.00'))

    def test_discount_by_admin_with_reason(self):
        self.assertEqual(
            self.client.post(f'{self.url}/discount/', {'amount': '1000', 'reason': 'Staff'}).status_code, 403
        )
        self.client.force_authenticate(make_user(Role.ADMIN))
        response = self.client.post(f'{self.url}/discount/', {'amount': '1000', 'reason': 'Staff family'})
        self.assertEqual((response.data['total'], response.data['discount_reason']), ('5000.00', 'Staff family'))
        self.assertEqual(self.client.post(f'{self.url}/discount/', {'amount': '9000', 'reason': 'x'}).status_code, 400)

    def test_lines_are_fixed_once_issued(self):
        self.client.post(f'{self.url}/issue/')
        add = self.client.post(f'{self.url}/lines/', {'description': 'Dressing', 'unit_price': '500'})
        self.assertEqual(add.status_code, status.HTTP_400_BAD_REQUEST)
        line_id = self.invoice['lines'][0]['id']
        void = self.client.post(f'{self.url}/lines/{line_id}/void/', {'reason': 'Error'})
        self.assertEqual(void.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manual_lines_and_voids_on_draft(self):
        added = self.client.post(f'{self.url}/lines/', {'description': 'Dressing', 'unit_price': '500', 'quantity': 2})
        self.assertEqual(added.data['total'], '7000.00')
        line_id = next(line['id'] for line in added.data['lines'] if line['description'] == 'Dressing')
        self.assertEqual(self.client.post(f'{self.url}/lines/{line_id}/void/', {}).status_code, 400)  # reason needed
        voided = self.client.post(f'{self.url}/lines/{line_id}/void/', {'reason': 'Not done'})
        self.assertEqual(voided.data['total'], '6000.00')

    def test_receipt(self):
        with schema_context('public'):
            Hospital.objects.filter(pk=self.tenant.pk).update(address='1 Hospital Road', currency='NGN')
        connection.set_tenant(self.tenant)
        payment = self.pay('2000', 'card', reference='POS-12').data
        receipt = self.client.get(f"/api/v1/billing/payments/{payment['id']}/receipt/").data
        self.assertEqual(receipt['hospital']['address'], '1 Hospital Road')
        self.assertEqual(
            (receipt['currency'], receipt['method'], receipt['balance_after']),
            ('NGN', 'Card / POS', Decimal('4000.00')),
        )
        self.assertEqual(receipt['patient']['mrn'], self.patient.mrn)

    def test_daily_summary(self):
        self.pay('1000', 'cash')
        self.pay('2000', 'transfer')
        summary = self.client.get('/api/v1/billing/summary/').data
        self.assertEqual(summary['payments']['total'], Decimal('3000.00'))
        self.assertEqual(summary['payments']['by_method'], {'cash': Decimal('1000.00'), 'transfer': Decimal('2000.00')})
        self.assertEqual(summary['payments']['by_cashier'][self.cashier.get_full_name()]['count'], 2)
        self.assertEqual(summary['charges']['by_category']['consultation'], Decimal('5000.00'))

    def test_who_can_do_what(self):
        self.client.force_authenticate(self.receptionist)
        self.assertEqual(self.pay('100').status_code, status.HTTP_201_CREATED)  # front desk collects
        self.assertEqual(self.client.post(f'{self.url}/issue/').status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.patient.user)
        invoices = self.client.get('/api/v1/billing/invoices/').data['results']
        self.assertEqual([i['id'] for i in invoices], [self.invoice['id']])
        self.assertEqual(self.pay('100').status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get('/api/v1/billing/invoices/').status_code, status.HTTP_403_FORBIDDEN)

    def test_void_invoice_requires_no_payments(self):
        self.pay('100')
        self.client.force_authenticate(make_user(Role.ADMIN))
        self.assertEqual(self.client.post(f'{self.url}/void/', {'reason': 'Wrong patient'}).status_code, 400)
        Payment.objects.update(voided=True)
        response = self.client.post(f'{self.url}/void/', {'reason': 'Wrong patient'})
        self.assertEqual((response.data['status'], response.data['total']), ('void', '0.00'))
