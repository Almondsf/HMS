from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Hospital(TenantMixin):
    '''
    A customer hospital. Each one has its own Postgres schema holding all of
    its users, patients and records. Lives in the shared (public) schema.
    '''

    class Plan(models.TextChoices):
        BASIC = 'basic', 'Basic'
        PRO = 'pro', 'Pro'
        ENTERPRISE = 'enterprise', 'Enterprise'

    # Controlled by the platform
    is_active = models.BooleanField(default=True, help_text='Suspended hospitals cannot be accessed.')
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.BASIC)
    created_at = models.DateTimeField(auto_now_add=True)

    # Editable by the hospital's own admin (GET/PATCH /api/hospital/)
    name = models.CharField(max_length=150)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    timezone = models.CharField(
        max_length=64, default='Africa/Lagos', help_text='API timestamps are shown in this timezone.'
    )
    currency = models.CharField(max_length=3, default='NGN', help_text='ISO 4217 code, e.g. NGN, GHS, KES')
    mrn_prefix = models.CharField(
        max_length=10, default='MRN', help_text='Prefix for patient medical record numbers, e.g. MRN-000123'
    )
    sms_booking_confirmations = models.BooleanField(default=False, help_text='SMS patients when they are booked')
    sms_reminders = models.BooleanField(default=False, help_text='SMS patients the day before an appointment')
    sms_sender_id = models.CharField(
        max_length=11, blank=True, help_text='Name patients see, e.g. STLUKES (must be registered with the provider)'
    )

    auto_create_schema = True
    auto_drop_schema = False  # deleting a hospital row must never silently drop patient data

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    '''Hostname that routes to a hospital, e.g. stlukes.hms.app.'''
