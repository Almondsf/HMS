from django.apps import AppConfig


class LabConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lab'

    def ready(self):
        from audit import registry

        from .models import LabTest, TestOrder, TestResult

        registry.register(LabTest)
        registry.register(TestOrder, patient=lambda order: order.patient_id)
        registry.register(TestResult, patient=lambda result: result.order.patient_id)
