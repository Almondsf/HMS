from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'

    def ready(self):
        from audit import registry

        from .models import User

        # Lockout counters change on every failed login; login events cover them
        registry.register(User, exclude=['failed_login_attempts', 'locked_until'])
