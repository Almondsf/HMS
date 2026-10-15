from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'

    def ready(self):
        from django.conf import settings
        from django.contrib import admin

        from audit import registry

        from .models import Hospital

        # Settings changes are recorded in the audit trail of whoever made them
        # (the hospital's own trail, or the platform's)
        registry.register(Hospital)

        admin.site.site_header = admin.site.site_title = f'{settings.PRODUCT_NAME} administration'
