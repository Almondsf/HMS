'''
Hospitals signing themselves up. Lives in the shared (public) schema.

Nothing is created until the email address is verified: a signup is only a
request until then, so spam costs an email, not a database schema.
'''

from django.db import models

from helpers.models import TrackingModel


class Signup(TrackingModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Waiting for email verification'
        PROVISIONING = 'provisioning', 'Setting up the hospital'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'

    hospital_name = models.CharField(max_length=150)
    address = models.CharField(max_length=40, db_index=True, help_text='Becomes <address>.<TENANT_BASE_DOMAIN>')
    plan = models.CharField(max_length=20)  # tenants.Hospital.Plan; the trial runs on it
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    password_hash = models.CharField(max_length=128, blank=True, help_text='Cleared once the hospital exists')
    token_hash = models.CharField(max_length=64, unique=True)  # sha256 of the emailed token
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    error = models.CharField(max_length=255, blank=True)
    login_url = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    # What they agreed to (legal.LegalDocument versions)
    terms_version = models.CharField(max_length=20, blank=True)
    privacy_version = models.CharField(max_length=20, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    provisioning_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    hospital = models.ForeignKey('tenants.Hospital', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.hospital_name} ({self.address}): {self.get_status_display()}'
