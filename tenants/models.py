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

    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True, help_text='Suspended hospitals cannot be accessed.')
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.BASIC)
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True
    auto_drop_schema = False  # deleting a hospital row must never silently drop patient data

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    '''Hostname that routes to a hospital, e.g. stlukes.hms.app.'''
