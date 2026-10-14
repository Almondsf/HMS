from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scheduling'

    def ready(self):
        from audit import registry

        from .models import Appointment

        registry.register(Appointment, patient=lambda appointment: appointment.patient_id)
