from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Patient messages'

    def ready(self):
        from . import handlers  # noqa: F401 (subscribes to appointment events)
