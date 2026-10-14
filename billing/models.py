from decimal import Decimal

from django.db import models
from django.db.models import OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from helpers.models import TrackingModel

MONEY = {'max_digits': 12, 'decimal_places': 2}
ZERO = Decimal('0.00')


class ServiceItem(TrackingModel):
    '''
    A chargeable service in the hospital's tariff: consultation fee, card fee,
    procedures. Lab tests and drugs are priced on their own records.
    '''

    class Category(models.TextChoices):
        REGISTRATION = 'registration', 'Registration / card'
        CONSULTATION = 'consultation', 'Consultation'
        PROCEDURE = 'procedure', 'Procedure'
        LAB = 'lab', 'Laboratory'
        PHARMACY = 'pharmacy', 'Pharmacy'
        OTHER = 'other', 'Other'

    class ChargeOn(models.TextChoices):
        MANUAL = 'manual', 'Added by the cashier'
        VISIT_OPENED = 'visit_opened', 'Every visit'
        CONSULTATION_RECORDED = 'consultation_recorded', 'Every consultation'

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    price = models.DecimalField(**MONEY)
    charge_on = models.CharField(
        max_length=30,
        choices=ChargeOn.choices,
        default=ChargeOn.MANUAL,
        help_text='Charge automatically when this happens (e.g. consultation fee on every consultation)',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.code} {self.name}'


class InvoiceQuerySet(models.QuerySet):
    def with_totals(self):
        """Annotate subtotal and amount paid in one query (avoids N+1 in lists)."""
        lines = (
            InvoiceLine.objects.filter(invoice=OuterRef('pk'), voided=False)
            .values('invoice')
            .annotate(total=Sum('amount'))
            .values('total')
        )
        payments = (
            Payment.objects.filter(invoice=OuterRef('pk'), voided=False)
            .values('invoice')
            .annotate(total=Sum('amount'))
            .values('total')
        )
        return self.annotate(
            _subtotal=Coalesce(Subquery(lines), Value(ZERO), output_field=models.DecimalField(**MONEY)),
            _paid=Coalesce(Subquery(payments), Value(ZERO), output_field=models.DecimalField(**MONEY)),
        )


class Invoice(TrackingModel):
    '''
    A patient's bill, usually for one visit. Charges collect on a draft;
    issuing it fixes the lines. Never deleted: void it instead.
    '''

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'  # still collecting charges
        ISSUED = 'issued', 'Issued'
        PAID = 'paid', 'Paid'
        VOID = 'void', 'Void'

    number = models.CharField(max_length=20, unique=True)
    patient = models.ForeignKey('profiles.PatientProfile', on_delete=models.PROTECT, related_name='invoices')
    visit = models.ForeignKey(
        'clinical.Visit', on_delete=models.PROTECT, null=True, blank=True, related_name='invoices'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    discount = models.DecimalField(**MONEY, default=ZERO)
    discount_reason = models.CharField(max_length=255, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # At most one draft per visit (or per patient for walk-in charges)
            models.UniqueConstraint(
                fields=['patient', 'visit'], condition=Q(status='draft'), name='one_draft_invoice_per_visit'
            ),
            models.UniqueConstraint(
                fields=['patient'],
                condition=Q(status='draft', visit__isnull=True),
                name='one_walk_in_draft_invoice_per_patient',
            ),
            models.CheckConstraint(condition=Q(discount__gte=0), name='invoice_discount_not_negative'),
        ]

    def __str__(self):
        return self.number

    @property
    def subtotal(self):
        if hasattr(self, '_subtotal'):
            return self._subtotal
        return self.lines.filter(voided=False).aggregate(total=Sum('amount'))['total'] or ZERO

    @property
    def total(self):
        return max(self.subtotal - self.discount, ZERO)

    @property
    def amount_paid(self):
        if hasattr(self, '_paid'):
            return self._paid
        return self.payments.filter(voided=False).aggregate(total=Sum('amount'))['total'] or ZERO

    def refresh_totals(self):
        """Drop cached annotations after lines or payments change."""
        for attribute in ('_subtotal', '_paid'):
            self.__dict__.pop(attribute, None)

    @property
    def balance(self):
        return self.total - self.amount_paid


class InvoiceLine(TrackingModel):
    '''One charge. Lines are never deleted or edited after issue: void and re-add.'''

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='lines')
    category = models.CharField(max_length=20, choices=ServiceItem.Category.choices)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(**MONEY)
    amount = models.DecimalField(**MONEY)
    needs_price = models.BooleanField(
        default=False, help_text='Charged at 0 because the item has no price yet; must be priced before issuing'
    )
    # What generated the charge, e.g. 'lab.testresult' #12; prevents charging it twice
    source_type = models.CharField(max_length=50, blank=True)
    source_id = models.CharField(max_length=50, blank=True)
    service_item = models.ForeignKey(ServiceItem, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    added_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['source_type', 'source_id'],
                condition=~Q(source_type='') & Q(voided=False),
                name='charge_each_source_once',
            )
        ]

    def __str__(self):
        return f'{self.quantity} x {self.description}'


class Payment(TrackingModel):
    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card / POS'
        TRANSFER = 'transfer', 'Bank transfer'
        MOBILE_MONEY = 'mobile_money', 'Mobile money'

    receipt_number = models.CharField(max_length=20, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(**MONEY)
    method = models.CharField(max_length=20, choices=Method.choices)
    reference = models.CharField(max_length=100, blank=True, help_text='POS / transfer reference')
    received_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name='payment_amount_positive')]

    def __str__(self):
        return self.receipt_number
