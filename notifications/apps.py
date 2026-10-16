from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Patient messages'

    def ready(self):
        from audit import registry

        from . import alerts, handlers  # noqa: F401 (subscribe to domain events)
        from .models import SmsMessage

        # Messages name the patient: changes and reads are audited against them
        registry.register(SmsMessage, patient=lambda message: message.patient_id)
