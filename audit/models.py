from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    '''
    Append-only record of who did what, to which record, when and from where.

    No foreign keys on purpose: events must outlive the users and records they
    describe, and must never be rewritten by a cascade. Rows can't be updated
    or deleted (enforced here and by a database trigger, see migration 0002).
    '''
    class Category(models.TextChoices):
        DATA_ACCESS = 'data_access', 'Data access'
        DATA_CHANGE = 'data_change', 'Data change'
        SECURITY = 'security', 'Security'
        DOMAIN = 'domain', 'Domain event'

    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    category = models.CharField(max_length=20, choices=Category.choices, db_index=True)
    action = models.CharField(max_length=64, db_index=True)

    actor_id = models.BigIntegerField(null=True, blank=True)
    actor_email = models.CharField(max_length=254, blank=True)
    actor_role = models.CharField(max_length=20, blank=True)

    resource_type = models.CharField(max_length=100, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    patient_id = models.BigIntegerField(null=True, blank=True, help_text='PatientProfile the record belongs to')

    changes = models.JSONField(default=dict, blank=True, help_text='{field: [old, new]}')
    metadata = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ['-occurred_at', '-id']
        indexes = [
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['patient_id', 'occurred_at']),
            models.Index(fields=['actor_id', 'occurred_at']),
        ]

    def __str__(self):
        target = f' {self.resource_type}#{self.resource_id}' if self.resource_type else ''
        return f'{self.occurred_at:%Y-%m-%d %H:%M:%S} {self.actor_email or "system"} {self.action}{target}'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError('Audit events are append-only.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError('Audit events are append-only.')
