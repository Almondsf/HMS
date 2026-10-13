'''Account security rules: login lockout and session revocation.'''

from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from audit.recorder import Category, record

from .models import User


def is_locked_out(user):
    return bool(user.locked_until and user.locked_until > timezone.now())


def record_failed_login(email):
    '''Count a failed attempt; lock the account once the limit is reached.'''
    users = User.objects.filter(email__iexact=email)
    users.update(failed_login_attempts=F('failed_login_attempts') + 1)
    locked = users.filter(failed_login_attempts__gte=settings.LOGIN_MAX_FAILED_ATTEMPTS).update(
        locked_until=timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES),
        failed_login_attempts=0,
    )

    user = users.first()
    # Unknown emails are logged too: credential-stuffing shows up as many of these
    record('login_failed', Category.SECURITY, actor=user, metadata={'email': email})
    if locked:
        record('account_locked', Category.SECURITY, actor=user, metadata={'minutes': settings.LOGIN_LOCKOUT_MINUTES})


def record_blocked_login(user):
    record('login_blocked', Category.SECURITY, actor=user, metadata={'locked_until': user.locked_until})


def record_successful_login(user):
    if user.failed_login_attempts or user.locked_until:
        User.objects.filter(pk=user.pk).update(failed_login_attempts=0, locked_until=None)
    record('login', Category.SECURITY, actor=user)


def revoke_all_sessions(user):
    '''Blacklist every refresh token issued to the user (e.g. after a password change).'''
    for token in OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True):
        BlacklistedToken.objects.get_or_create(token=token)
