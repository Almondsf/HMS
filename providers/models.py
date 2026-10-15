'''
Which company delivers the platform's email and SMS, switchable at runtime
(by a platform operator, without a deploy). Lives in the shared schema.

Secrets (API keys, passwords) are stored encrypted with PROVIDER_ENCRYPTION_KEY
and never returned by the API.
'''

from django.db import models

from helpers.models import TrackingModel


class Channel(models.TextChoices):
    EMAIL = 'email', 'Email'
    SMS = 'sms', 'SMS'


class ProviderConfig(TrackingModel):
    channel = models.CharField(max_length=10, choices=Channel.choices)
    provider = models.CharField(max_length=30)  # a key of providers.registry.PROVIDERS
    settings = models.JSONField(default=dict, blank=True)  # non-secret settings
    encrypted_secrets = models.TextField(blank=True)  # Fernet token of a JSON object
    is_active = models.BooleanField(default=False)
    # A provider can only be switched on after a successful test of its current settings
    last_test_ok = models.BooleanField(null=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['channel', 'provider']
        constraints = [
            models.UniqueConstraint(fields=['channel', 'provider'], name='one_config_per_provider'),
            models.UniqueConstraint(
                fields=['channel'], condition=models.Q(is_active=True), name='one_active_provider_per_channel'
            ),
        ]

    def __str__(self):
        return f'{self.get_channel_display()}: {self.provider}{" (active)" if self.is_active else ""}'
