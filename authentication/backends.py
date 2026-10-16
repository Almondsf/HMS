'''
Every password sign-in (the API and the Django admin alike) goes through
this backend, so account lockout and failed-attempt logging can't be
bypassed by signing in somewhere else.
'''

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from . import services


class LockoutModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        username = username if username is not None else kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        known = User.objects.filter(email__iexact=username).first()
        if known is not None and services.is_locked_out(known):
            services.record_blocked_login(known)
            return None  # refused even with the right password
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is None:
            services.record_failed_login(username)
        else:
            services.record_successful_login(user)
        return user
