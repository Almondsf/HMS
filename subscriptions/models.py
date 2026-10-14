'''
What hospitals pay for the platform. Lives in the shared (public) schema.

A hospital's access follows its subscription:
  trialing / active            full access
  past_due (within grace)      full access, with a warning
  past_due (after grace)       read-only: records stay viewable, nothing new is created
  cancelled (after period end) read-only
Suspension (Hospital.is_active=False) stays a separate, manual platform action.
'''

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from helpers.models import TrackingModel


class Interval(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    YEARLY = 'yearly', 'Yearly'


class PlanPrice(TrackingModel):
    '''The price of a plan for a billing interval. Edit prices in the platform admin.'''

    plan = models.CharField(max_length=20)  # tenants.Hospital.Plan
    interval = models.CharField(max_length=10, choices=Interval.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='In naira')
    currency = models.CharField(max_length=3, default='NGN')
    paystack_plan_code = models.CharField(
        max_length=50, blank=True, help_text='Created by `manage.py sync_paystack_plans`'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['plan', 'interval']
        constraints = [models.UniqueConstraint(fields=['plan', 'interval'], name='one_price_per_plan_interval')]

    def __str__(self):
        return f'{self.plan} {self.interval}: {self.currency} {self.amount:,.2f}'

    @property
    def amount_kobo(self):
        return int(self.amount * 100)


class Subscription(TrackingModel):
    class Status(models.TextChoices):
        TRIALING = 'trialing', 'Free trial'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Payment overdue'
        CANCELLED = 'cancelled', 'Cancelled'

    class Access(models.TextChoices):
        FULL = 'full', 'Full access'
        WARNING = 'warning', 'Full access, payment overdue'
        READ_ONLY = 'read_only', 'Read-only'

    hospital = models.OneToOneField('tenants.Hospital', on_delete=models.CASCADE, related_name='subscription')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIALING, db_index=True)
    interval = models.CharField(max_length=10, choices=Interval.choices, default=Interval.MONTHLY)
    current_period_end = models.DateTimeField(help_text='Paid (or trial) access runs until this moment')
    billing_email = models.EmailField(blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    paystack_customer_code = models.CharField(max_length=50, blank=True, db_index=True)
    paystack_subscription_code = models.CharField(max_length=50, blank=True, db_index=True)
    paystack_email_token = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f'{self.hospital}: {self.get_status_display()} until {self.current_period_end:%Y-%m-%d}'

    @property
    def grace_ends_at(self):
        return self.current_period_end + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)

    def access(self, now=None):
        now = now or timezone.now()
        if now <= self.current_period_end:
            return self.Access.FULL
        if self.status != self.Status.CANCELLED and now <= self.grace_ends_at:
            return self.Access.WARNING
        return self.Access.READ_ONLY

    def days_left(self, now=None):
        return max((self.current_period_end - (now or timezone.now())).days, 0)


class SubscriptionPayment(TrackingModel):
    '''A payment towards a subscription: Paystack (card/bank) or recorded manually (transfer).'''

    class Source(models.TextChoices):
        PAYSTACK = 'paystack', 'Paystack'
        MANUAL = 'manual', 'Recorded by the platform (e.g. bank transfer)'

    hospital = models.ForeignKey('tenants.Hospital', on_delete=models.PROTECT, related_name='subscription_payments')
    reference = models.CharField(max_length=100, unique=True)  # idempotency: each payment counts once
    source = models.CharField(max_length=20, choices=Source.choices)
    plan = models.CharField(max_length=20)
    interval = models.CharField(max_length=10, choices=Interval.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    paid_at = models.DateTimeField()
    period_end = models.DateTimeField(help_text='Access paid up to this moment by this payment')
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.CharField(max_length=254, blank=True)

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f'{self.hospital} {self.currency} {self.amount:,.2f} ({self.reference})'
