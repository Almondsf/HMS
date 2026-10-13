from django.apps import AppConfig


class ClinicalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clinical'

    def ready(self):
        from audit import registry

        from .models import Consultation, Prescription, Visit

        registry.register(Visit, patient=lambda visit: visit.patient_id)
        registry.register(Consultation, patient=lambda consultation: consultation.visit.patient_id)
        registry.register(Prescription, patient=lambda prescription: prescription.consultation.visit.patient_id)
