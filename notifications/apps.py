from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Patient messages'

    def ready(self):
        from . import alerts, handlers  # noqa: F401 (subscribe to domain events)
