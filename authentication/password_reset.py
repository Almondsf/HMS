'''
Password resets: by an admin (temporary password) or by email link.

Email links use Django's reset tokens, which are single-use (they hash the
current password) and expire after PASSWORD_RESET_TIMEOUT. Tokens are also
bound to the hospital, so a link can never be replayed at another hospital
against a different user with the same id.
'''

import secrets
import string

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import connection, transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from audit.recorder import Category, record

from . import services
from .models import User


class HospitalTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f'{connection.schema_name}:{super()._make_hash_value(user, timestamp)}'


token_generator = HospitalTokenGenerator()


def _set_new_password(user, password, *, must_change):
    user.set_password(password)
    user.must_change_password = must_change
    user.failed_login_attempts, user.locked_until = 0, None
    user.save(update_fields=['password', 'must_change_password', 'failed_login_attempts', 'locked_until'])
    services.revoke_all_sessions(user)


def temporary_password():
    '''Readable but strong: e.g. "Kx7m-Pq2r-Tz9w" (no look-alike characters).'''
    alphabet = ''.join(c for c in string.ascii_letters + string.digits if c not in 'O0Il1')
    return '-'.join(''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


@transaction.atomic
def reset_by_admin(*, user, by):
    '''Give a staff member a temporary password they must change at next sign-in.'''
    if user.pk == by.pk:
        raise ValidationError('Use "Change password" for your own account.')
    if user.user_type == User.UserType.PATIENT:
        raise ValidationError("Patients don't sign in to the staff app.")
    password = temporary_password()
    _set_new_password(user, password, must_change=True)
    record('password_reset_by_admin', Category.SECURITY, resource=user, metadata={'user_id': user.pk})
    return password


def _reset_link(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    host = request.get_host()
    if settings.FRONTEND_URL:
        base = settings.FRONTEND_URL.format(subdomain=host.split('.')[0], host=host)
    else:
        base = f'{request.scheme}://{host}'  # the app is served from the hospital's own address
    return f'{base.rstrip("/")}/reset-password?uid={uid}&token={token}'


def request_reset(*, email, request):
    '''
    Email a reset link if an account with a password exists. The caller
    always gets the same answer, so this can't be used to find accounts.
    '''
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or not user.has_usable_password():
        record('password_reset_requested', Category.SECURITY, metadata={'email': email, 'account': False})
        return
    hospital = getattr(connection.tenant, 'name', 'HMS')
    send_mail(
        subject=f'Reset your {hospital} password',
        message=(
            f'Hello {user.first_name},\n\n'
            f'Someone asked to reset the password for your {hospital} account. '
            f'Use this link within {settings.PASSWORD_RESET_TIMEOUT // 60} minutes:\n\n'
            f'{_reset_link(request, user)}\n\n'
            "If it wasn't you, ignore this email: your password stays the same."
        ),
        from_email=None,
        recipient_list=[user.email],
    )
    record('password_reset_requested', Category.SECURITY, actor=user, metadata={'account': True})


@transaction.atomic
def complete_reset(*, uid, token, new_password):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is None or not token_generator.check_token(user, token):
        raise ValidationError({'token': 'This reset link is invalid or has expired. Request a new one.'})
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise ValidationError({'new_password': exc.messages}) from exc
    _set_new_password(user, new_password, must_change=False)
    record('password_reset_completed', Category.SECURITY, actor=user)
    return user
