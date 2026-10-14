from django.apps import AppConfig


class InsuranceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'insurance'

    def ready(self):
        from audit import registry

        from .models import Claim, Coverage, InsuranceProvider

        registry.register(InsuranceProvider)
        registry.register(Coverage, patient=lambda coverage: coverage.patient_id)
        registry.register(Claim, patient=lambda claim: claim.invoice.patient_id)
