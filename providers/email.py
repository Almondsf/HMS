'''
Django's email backend for the whole platform: every send_mail goes through
the active email provider, or the server's EMAIL_BACKEND settings without one.
'''

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

from . import services
from .models import Channel


class ProviderEmailBackend(BaseEmailBackend):
    def send_messages(self, messages):
        if not messages:
            return 0
        provider = services.active(Channel.EMAIL)
        if provider is None:
            fallback = get_connection(settings.FALLBACK_EMAIL_BACKEND, fail_silently=self.fail_silently)
            return fallback.send_messages(messages)
        try:
            return provider.send_messages(messages)
        except Exception:
            if self.fail_silently:
                return 0
            raise
