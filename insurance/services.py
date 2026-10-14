'''
Insurance claims. While a claim is open its amount is set aside: the patient
only pays the rest. A rejection (or a short payment) returns the difference
to the patient's balance.
'''

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from audit import events
from billing import services as billing_services
from billing.models import Invoice, Payment
from profiles.services import next_record_number

from .models import Claim

CENT = Decimal('0.01')


def _service_date(invoice):
    return timezone.localdate(invoice.visit.visit_date if invoice.visit_id else invoice.created_at)


@transaction.atomic
def create_claim(*, invoice, coverage, authorization_code=''):
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != Invoice.Status.ISSUED:
        raise ValidationError('Issue the invoice before claiming from the insurer.')
    if coverage.patient_id != invoice.patient_id:
        raise ValidationError({'coverage': "This cover belongs to another patient."})
    if not coverage.provider.is_active:
        raise ValidationError({'coverage': f'{coverage.provider} is no longer accepted.'})
    if not coverage.is_valid_on(_service_date(invoice)):
        raise ValidationError({'coverage': 'The cover was not valid on the date of service.'})
    if coverage.provider.requires_authorization and not authorization_code:
        raise ValidationError({'authorization_code': f'{coverage.provider} requires a pre-authorisation code.'})
    if invoice.claims.filter(status__in=Claim.OPEN_STATUSES).exists():
        raise ValidationError('This invoice already has an open claim.')

    percent = Decimal(str(coverage.effective_percent))
    amount = (invoice.patient_due * percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValidationError('Nothing left on this invoice for the insurer to cover.')
    claim = Claim.objects.create(
        number=next_record_number('claim', 'CLM'),
        invoice=invoice,
        coverage=coverage,
        claimed_amount=amount,
        authorization_code=authorization_code,
    )
    events.publish('insurance.claim_created', resource=claim, amount=amount, provider=coverage.provider.code)
    return claim


def _require(claim, *statuses, action):
    if claim.status not in statuses:
        raise ValidationError(f"Can't {action}: claim {claim.number} is {claim.get_status_display().lower()}.")


@transaction.atomic
def submit_claim(*, claim):
    _require(claim, Claim.Status.DRAFT, action='submit')
    claim.status, claim.submitted_at = Claim.Status.SUBMITTED, timezone.now()
    claim.save(update_fields=['status', 'submitted_at', 'updated_at'])
    events.publish('insurance.claim_submitted', resource=claim)
    return claim


@transaction.atomic
def record_response(*, claim, approved_amount=None, rejection_reason=''):
    '''The insurer's decision: approve all or part of the claim, or reject it.'''
    _require(claim, Claim.Status.SUBMITTED, action='record a response')
    if rejection_reason:
        claim.status, claim.rejection_reason = Claim.Status.REJECTED, rejection_reason
    else:
        if approved_amount is None or not 0 < approved_amount <= claim.claimed_amount:
            raise ValidationError({'approved_amount': f'Between 0 and the claimed {claim.claimed_amount}.'})
        claim.status, claim.approved_amount = Claim.Status.APPROVED, approved_amount
    claim.responded_at = timezone.now()
    claim.save(update_fields=['status', 'approved_amount', 'rejection_reason', 'responded_at', 'updated_at'])
    events.publish(f'insurance.claim_{claim.status}', resource=claim, approved_amount=claim.approved_amount)
    return claim


@transaction.atomic
def record_claim_payment(*, claim, amount, by, reference=''):
    '''
    The insurer paid. Any shortfall against the approved amount falls back
    to the patient, since the claim is closed.
    '''
    _require(claim, Claim.Status.SUBMITTED, Claim.Status.APPROVED, action='record a payment')
    expected = claim.approved_amount or claim.claimed_amount
    if not 0 < amount <= expected:
        raise ValidationError({'amount': f'Between 0 and {expected}.'})
    payment = billing_services.record_payment(
        invoice=claim.invoice, amount=amount, method=Payment.Method.INSURANCE, by=by, reference=reference
    )
    claim.status, claim.paid_amount, claim.paid_at, claim.payment = Claim.Status.PAID, amount, timezone.now(), payment
    claim.save(update_fields=['status', 'paid_amount', 'paid_at', 'payment', 'updated_at'])
    events.publish('insurance.claim_paid', resource=claim, amount=amount, shortfall=expected - amount)
    return claim


def claim_document(claim):
    '''What insurers ask for: member, encounter, ICD-10 diagnoses and itemised charges.'''
    from clinical.models import Diagnosis

    invoice, coverage = claim.invoice, claim.coverage
    patient = invoice.patient
    diagnoses = []
    if invoice.visit_id:
        diagnoses = [
            {'code': d.code_id, 'description': d.description, 'kind': d.kind, 'certainty': d.certainty}
            for d in Diagnosis.objects.filter(consultation__visit=invoice.visit)
            .exclude(certainty=Diagnosis.Certainty.RULED_OUT)
            .order_by('kind', 'id')
        ]
    return {
        'claim_number': claim.number,
        'status': claim.status,
        'provider': {'name': coverage.provider.name, 'code': coverage.provider.code},
        'member': {
            'member_number': coverage.member_number,
            'plan': coverage.plan_name,
            'name': patient.user.get_full_name(),
            'date_of_birth': patient.user.date_of_birth,
            'gender': patient.user.gender,
            'mrn': patient.mrn,
        },
        'service_date': _service_date(invoice),
        'attending_doctor': invoice.visit.assigned_doctor.user.get_full_name() if invoice.visit_id else None,
        'authorization_code': claim.authorization_code,
        'diagnoses': diagnoses,
        'lines': [
            {
                'description': line.description,
                'category': line.category,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'amount': line.amount,
            }
            for line in invoice.lines.filter(voided=False)
        ],
        'invoice_number': invoice.number,
        'invoice_total': invoice.total,
        'coverage_percent': coverage.effective_percent,
        'claimed_amount': claim.claimed_amount,
    }


def outstanding_by_provider():
    '''Money insurers still owe, per provider and claim status (for chasing payment).'''
    rows = (
        Claim.objects.filter(status__in=Claim.OPEN_STATUSES)
        .values('coverage__provider__name', 'status')
        .annotate(count=Count('id'), amount=Sum('claimed_amount'), approved=Sum('approved_amount'))
        .order_by('coverage__provider__name', 'status')
    )
    summary = {}
    for row in rows:
        provider = summary.setdefault(row['coverage__provider__name'], {'total': Decimal('0'), 'by_status': {}})
        owed = row['approved'] if row['status'] == Claim.Status.APPROVED else row['amount']
        provider['by_status'][row['status']] = {'count': row['count'], 'amount': owed}
        provider['total'] += owed
    return summary
