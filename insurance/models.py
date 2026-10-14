from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from billing.models import MONEY, ZERO
from helpers.models import TrackingModel

PERCENT = {
    'max_digits': 5,
    'decimal_places': 2,
    'validators': [MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
}


class InsuranceProvider(TrackingModel):
    '''An HMO, the NHIA scheme, a private insurer or a company paying for its staff.'''

    class Kind(models.TextChoices):
        HMO = 'hmo', 'HMO'
        NHIA = 'nhia', 'NHIA (national scheme)'
        PRIVATE = 'private', 'Private insurer'
        CORPORATE = 'corporate', 'Corporate retainer'

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=30, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.HMO)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    default_coverage_percent = models.DecimalField(**PERCENT, default=Decimal('100'))
    requires_authorization = models.BooleanField(
        default=False, help_text='Claims need a pre-authorisation code from the provider'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Coverage(TrackingModel):
    '''A patient's membership of an insurance scheme.'''

    patient = models.ForeignKey('profiles.PatientProfile', on_delete=models.PROTECT, related_name='coverages')
    provider = models.ForeignKey(InsuranceProvider, on_delete=models.PROTECT, related_name='coverages')
    member_number = models.CharField(max_length=50)
    plan_name = models.CharField(max_length=100, blank=True)
    coverage_percent = models.DecimalField(
        **PERCENT, null=True, blank=True, help_text="Leave blank to use the provider's default"
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True, help_text='Blank: no end date')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-valid_from']
        constraints = [
            models.UniqueConstraint(fields=['provider', 'member_number'], name='unique_member_number_per_provider'),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=models.F('valid_from')),
                name='coverage_ends_after_it_starts',
            ),
        ]

    def __str__(self):
        return f'{self.provider} #{self.member_number}'

    @property
    def effective_percent(self):
        return self.coverage_percent if self.coverage_percent is not None else self.provider.default_coverage_percent

    def is_valid_on(self, day):
        return self.is_active and self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class Claim(TrackingModel):
    '''A request to an insurer to pay its share of an invoice.'''

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PAID = 'paid', 'Paid'

    # Claims whose amount the patient is not expected to pay
    OPEN_STATUSES = (Status.DRAFT, Status.SUBMITTED, Status.APPROVED)

    number = models.CharField(max_length=20, unique=True)
    invoice = models.ForeignKey('billing.Invoice', on_delete=models.PROTECT, related_name='claims')
    coverage = models.ForeignKey(Coverage, on_delete=models.PROTECT, related_name='claims')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    claimed_amount = models.DecimalField(**MONEY)
    approved_amount = models.DecimalField(**MONEY, null=True, blank=True)
    paid_amount = models.DecimalField(**MONEY, default=ZERO)
    authorization_code = models.CharField(max_length=50, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment = models.OneToOneField(
        'billing.Payment', on_delete=models.PROTECT, null=True, blank=True, related_name='insurance_claim'
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # One live claim per invoice; after a rejection a new one can be made
            models.UniqueConstraint(
                fields=['invoice'], condition=~Q(status='rejected'), name='one_live_claim_per_invoice'
            ),
            models.CheckConstraint(condition=Q(claimed_amount__gt=0), name='claim_amount_positive'),
        ]

    def __str__(self):
        return self.number
