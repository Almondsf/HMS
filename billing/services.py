'''
Billing rules. Charges arrive automatically from clinical events (see
billing.handlers) or are added by the cashier; payments are taken against
invoices. Money is never deleted: lines, payments and invoices are voided.
'''

from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.utils import timezone

from audit import events
from profiles.services import next_record_number

from .models import ZERO, Invoice, InvoiceLine, Payment, ServiceItem

Status = Invoice.Status


def _draft_invoice(*, patient, visit):
    '''The open (draft) invoice for this visit, or for the patient's walk-in charges.'''
    drafts = Invoice.objects.select_for_update().filter(patient=patient, visit=visit, status=Status.DRAFT)
    invoice = drafts.first()
    if invoice is not None:
        return invoice
    try:
        with transaction.atomic():
            return Invoice.objects.create(number=next_record_number('invoice', 'INV'), patient=patient, visit=visit)
    except IntegrityError:  # created concurrently by another request
        return drafts.get()


@transaction.atomic
def add_charge(
    *, patient, visit, category, description, unit_price, quantity=1, source=None, service_item=None, by=None
):
    '''
    Add a charge to the patient's draft invoice. A missing price is charged
    at 0 and flagged, so billing setup never blocks patient care. `source`
    (type, id) makes the charge idempotent: each source is billed once.
    '''
    source_type, source_id = (source[0], str(source[1])) if source else ('', '')
    if source_type:
        existing = InvoiceLine.objects.filter(source_type=source_type, source_id=source_id, voided=False).first()
        if existing is not None:
            return existing

    needs_price = unit_price is None
    unit_price = ZERO if needs_price else Decimal(unit_price)
    invoice = _draft_invoice(patient=patient, visit=visit)
    return InvoiceLine.objects.create(
        invoice=invoice,
        category=category,
        description=description[:255],
        quantity=quantity,
        unit_price=unit_price,
        amount=unit_price * quantity,
        needs_price=needs_price,
        source_type=source_type,
        source_id=source_id,
        service_item=service_item,
        added_by=by,
    )


def charge_service_items(*, charge_on, patient, visit, source_type, source_id):
    '''Charge every active tariff item configured for this trigger (e.g. consultation fee).'''
    for item in ServiceItem.objects.filter(charge_on=charge_on, is_active=True):
        add_charge(
            patient=patient,
            visit=visit,
            category=item.category,
            description=item.name,
            unit_price=item.price,
            service_item=item,
            source=(source_type, f'{source_id}:{item.code}'),
        )


def _require_status(invoice, *allowed, action):
    if invoice.status not in allowed:
        raise ValidationError(f"Can't {action}: invoice {invoice.number} is {invoice.get_status_display().lower()}.")


@transaction.atomic
def create_invoice(*, patient, visit=None):
    '''Open (or return) the draft invoice, e.g. for over-the-counter charges.'''
    return _draft_invoice(patient=patient, visit=visit)


@transaction.atomic
def add_manual_line(*, invoice, by, service_item=None, description='', unit_price=None, quantity=1):
    _require_status(invoice, Status.DRAFT, action='add charges')
    if service_item is not None:
        if not service_item.is_active:
            raise ValidationError({'service_item': 'This service is no longer offered.'})
        description, unit_price, category = service_item.name, service_item.price, service_item.category
    else:
        if not description or unit_price is None:
            raise ValidationError('Choose a service item, or give a description and a price.')
        category = ServiceItem.Category.OTHER
    if quantity < 1:
        raise ValidationError({'quantity': 'Must be at least 1.'})
    return InvoiceLine.objects.create(
        invoice=invoice,
        category=category,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        amount=Decimal(unit_price) * quantity,
        service_item=service_item,
        added_by=by,
    )


@transaction.atomic
def price_line(*, line, unit_price):
    '''Set the price of a line charged without one (e.g. a drug with no price yet).'''
    _require_status(line.invoice, Status.DRAFT, action='change prices')
    if line.voided:
        raise ValidationError('This line was voided.')
    line.unit_price, line.amount, line.needs_price = unit_price, unit_price * line.quantity, False
    line.save(update_fields=['unit_price', 'amount', 'needs_price', 'updated_at'])
    return line


@transaction.atomic
def void_line(*, line, reason):
    _require_status(line.invoice, Status.DRAFT, action='remove charges')
    if not reason:
        raise ValidationError({'reason': 'Give a reason.'})
    if line.voided:
        raise ValidationError('This line is already voided.')
    line.voided, line.void_reason = True, reason
    line.save(update_fields=['voided', 'void_reason', 'updated_at'])
    return line


@transaction.atomic
def apply_discount(*, invoice, amount, reason):
    _require_status(invoice, Status.DRAFT, Status.ISSUED, action='discount')
    if not reason:
        raise ValidationError({'reason': 'Give a reason for the discount.'})
    if amount < 0 or amount > invoice.subtotal:
        raise ValidationError({'amount': f'Must be between 0 and the subtotal ({invoice.subtotal}).'})
    if invoice.subtotal - amount < invoice.amount_paid:
        raise ValidationError({'amount': 'The discount would make the invoice less than what has been paid.'})
    invoice.discount, invoice.discount_reason = amount, reason
    invoice.save(update_fields=['discount', 'discount_reason', 'updated_at'])
    _settle(invoice)
    return invoice


@transaction.atomic
def issue_invoice(*, invoice):
    '''Finalise the charges and present the bill.'''
    _require_status(invoice, Status.DRAFT, action='issue')
    lines = invoice.lines.filter(voided=False)
    if not lines.exists():
        raise ValidationError('The invoice has no charges.')
    unpriced = list(lines.filter(needs_price=True).values_list('description', flat=True))
    if unpriced:
        raise ValidationError(f"Set prices first for: {', '.join(unpriced)}")
    invoice.status, invoice.issued_at = Status.ISSUED, timezone.now()
    invoice.save(update_fields=['status', 'issued_at', 'updated_at'])
    events.publish('billing.invoice_issued', resource=invoice, total=invoice.total)
    _settle(invoice)
    return invoice


def _settle(invoice):
    '''An issued invoice with nothing left to pay becomes paid (and back, if a payment is voided).'''
    invoice.refresh_totals()
    if invoice.status == Status.ISSUED and invoice.balance <= 0:
        invoice.status = Status.PAID
    elif invoice.status == Status.PAID and invoice.balance > 0:
        invoice.status = Status.ISSUED
    else:
        return
    invoice.save(update_fields=['status', 'updated_at'])
    if invoice.status == Status.PAID:
        events.publish('billing.invoice_paid', resource=invoice)


@transaction.atomic
def record_payment(*, invoice, amount, method, by, reference=''):
    # Lock the invoice: a double-submitted payment waits, then sees the new balance
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    _require_status(invoice, Status.DRAFT, Status.ISSUED, action='take payment')
    if amount <= 0:
        raise ValidationError({'amount': 'Must be more than 0.'})
    if amount > invoice.balance:
        raise ValidationError({'amount': f'More than the balance due ({invoice.balance}).'})
    payment = Payment.objects.create(
        receipt_number=next_record_number('receipt', 'RCT'),
        invoice=invoice,
        amount=amount,
        method=method,
        reference=reference,
        received_by=by,
    )
    events.publish('billing.payment_received', resource=payment, amount=amount, method=method)
    _settle(invoice)
    return payment


@transaction.atomic
def void_payment(*, payment, reason):
    '''Reverse a payment recorded in error (or refunded).'''
    if not reason:
        raise ValidationError({'reason': 'Give a reason.'})
    if payment.voided:
        raise ValidationError('This payment is already voided.')
    payment.voided, payment.void_reason = True, reason
    payment.save(update_fields=['voided', 'void_reason', 'updated_at'])
    events.publish('billing.payment_voided', resource=payment, amount=payment.amount)
    _settle(Invoice.objects.select_for_update().get(pk=payment.invoice_id))
    return payment


@transaction.atomic
def void_invoice(*, invoice, reason):
    _require_status(invoice, Status.DRAFT, Status.ISSUED, action='void')
    if not reason:
        raise ValidationError({'reason': 'Give a reason.'})
    if invoice.amount_paid > 0:
        raise ValidationError('Void its payments first.')
    invoice.lines.filter(voided=False).update(voided=True, void_reason=f'Invoice voided: {reason}')
    invoice.status, invoice.void_reason = Status.VOID, reason
    invoice.save(update_fields=['status', 'void_reason', 'updated_at'])
    events.publish('billing.invoice_voided', resource=invoice)
    return invoice


def daily_summary(day):
    '''Money taken on a day (hospital time): totals by method and cashier, charges by category.'''
    payments = Payment.objects.filter(voided=False, created_at__date=day)
    by_method = {row['method']: row['total'] for row in payments.values('method').annotate(total=Sum('amount'))}
    by_cashier = defaultdict(lambda: {'count': 0, 'total': ZERO})
    for row in payments.values('received_by__first_name', 'received_by__last_name').annotate(
        total=Sum('amount'), count=Count('id')
    ):
        name = f"{row['received_by__first_name'] or ''} {row['received_by__last_name'] or ''}".strip() or 'Unknown'
        by_cashier[name] = {'count': row['count'], 'total': row['total']}
    charges = InvoiceLine.objects.filter(voided=False, created_at__date=day)
    by_category = {row['category']: row['total'] for row in charges.values('category').annotate(total=Sum('amount'))}
    return {
        'date': day,
        'payments': {
            'count': payments.count(),
            'total': payments.aggregate(total=Sum('amount'))['total'] or ZERO,
            'by_method': by_method,
            'by_cashier': dict(by_cashier),
        },
        'charges': {'total': sum(by_category.values(), ZERO), 'by_category': by_category},
        'outstanding_invoices': Invoice.objects.filter(status=Status.ISSUED).count(),
    }
