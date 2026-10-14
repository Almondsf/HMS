from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'billing'

    def ready(self):
        from audit import registry

        from . import handlers  # noqa: F401  (subscribes the automatic charges)
        from .models import Invoice, InvoiceLine, Payment, ServiceItem

        registry.register(ServiceItem)
        registry.register(Invoice, patient=lambda invoice: invoice.patient_id)
        registry.register(InvoiceLine, patient=lambda line: line.invoice.patient_id)
        registry.register(Payment, patient=lambda payment: payment.invoice.patient_id)
