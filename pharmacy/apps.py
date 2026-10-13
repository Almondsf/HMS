from django.apps import AppConfig


class PharmacyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pharmacy'

    def ready(self):
        from audit import registry

        from .models import DispensedItem, DispenseTransaction, Drug

        registry.register(Drug)
        registry.register(DispenseTransaction)
        registry.register(DispensedItem, patient=lambda item: item.prescription.consultation.visit.patient_id)
