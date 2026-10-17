'''
Two-factor sign-in: a 6-digit code from an authenticator app (TOTP, RFC
6238), or a single-use recovery code, after the password.

Platform operators and hospital admins must use it when TWO_FACTOR_REQUIRED
is on (production); everyone else may. Until someone who must use it has set
it up, they can only reach the sign-in endpoints (see tokens.py).
'''

import hashlib
import hmac
import re
import secrets
import time

import pyotp
import segno
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name

from audit.recorder import Category, record

from .models import TwoFactor, User

RECOVERY_CODES = 10
CHALLENGE_SALT = 'hms.two-factor-challenge'
CHALLENGE_SECONDS = 5 * 60
STEP = 30  # seconds per code


def required_for(user):
    return bool(settings.TWO_FACTOR_REQUIRED and (user.is_superuser or user.user_type == User.UserType.ADMIN))


def is_enabled(user):
    return TwoFactor.objects.filter(user=user, confirmed_at__isnull=False).exists()


def setup_required(user):
    return required_for(user) and not is_enabled(user)


def status(user):
    device = TwoFactor.objects.filter(user=user, confirmed_at__isnull=False).first()
    return {
        'enabled': device is not None,
        'required': required_for(user),
        'recovery_codes_left': len(device.recovery_codes) if device else 0,
    }


# ---- Setting it up ----


def _issuer():
    hospital = getattr(connection.tenant, 'name', '')
    if hospital and connection.schema_name != get_public_schema_name():
        return f'{settings.PRODUCT_NAME} ({hospital})'
    return settings.PRODUCT_NAME


def begin_setup(user):
    '''A new secret to scan; not active until confirmed with a code.'''
    if is_enabled(user):
        raise ValidationError('Two-factor sign-in is already on. Turn it off first to move it to a new phone.')
    secret = pyotp.random_base32()
    TwoFactor.objects.update_or_create(
        user=user, defaults={'secret': secret, 'confirmed_at': None, 'last_used_step': None, 'recovery_codes': []}
    )
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=_issuer())
    return {'secret': secret, 'otpauth_uri': uri, 'qr_code': segno.make(uri, error='m').svg_data_uri(scale=5, border=2)}


def _hash(code):
    return hashlib.sha256(_normalize(code).encode()).hexdigest()


def _normalize(code):
    return re.sub(r'[\s-]', '', str(code or '')).lower()


def _new_recovery_codes():
    alphabet = 'abcdefghjkmnpqrstuvwxyz23456789'  # no look-alikes
    return [
        '-'.join(''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2)) for _ in range(RECOVERY_CODES)
    ]


def _matching_step(secret, code, now=None):
    '''The time step a 6-digit code belongs to (this one, or one either side), or None.'''
    totp = pyotp.TOTP(secret)
    now = now or time.time()
    for offset in (0, -1, 1):
        moment = now + offset * STEP
        if hmac.compare_digest(totp.at(moment), code):
            return int(moment // STEP)
    return None


@transaction.atomic
def confirm_setup(user, code):
    '''Turn it on once the app's code checks out. Returns the recovery codes (shown once).'''
    device = TwoFactor.objects.select_for_update().filter(user=user, confirmed_at__isnull=True).first()
    if device is None:
        raise ValidationError('Start the setup first.')
    step = _matching_step(device.secret, _normalize(code))
    if step is None:
        raise ValidationError({'code': "That code doesn't match. Check the phone's time is set automatically."})
    codes = _new_recovery_codes()
    device.confirmed_at, device.last_used_step = timezone.now(), step
    device.recovery_codes = [_hash(c) for c in codes]
    device.save()
    record('two_factor_enabled', Category.SECURITY, actor=user)
    return codes


# ---- Signing in ----


@transaction.atomic
def verify(user, code):
    '''A current authenticator code (each usable once) or an unused recovery code.'''
    device = TwoFactor.objects.select_for_update().filter(user=user, confirmed_at__isnull=False).first()
    code = _normalize(code)
    if device is None or not code:
        return False
    if re.fullmatch(r'\d{6}', code):
        step = _matching_step(device.secret, code)
        if step is None or (device.last_used_step is not None and step <= device.last_used_step):
            return False  # wrong, or already used: a code seen over someone's shoulder can't be replayed
        device.last_used_step = step
        device.save(update_fields=['last_used_step'])
        return True
    hashed = _hash(code)
    if hashed in device.recovery_codes:
        device.recovery_codes = [h for h in device.recovery_codes if h != hashed]
        device.save(update_fields=['recovery_codes'])
        record(
            'two_factor_recovery_code_used', Category.SECURITY, actor=user,
            metadata={'left': len(device.recovery_codes)},
        )  # fmt: skip
        return True
    return False


def challenge_for(user):
    '''Proof that the password was right, valid for 5 minutes at this hospital only.'''
    return signing.dumps({'user': user.pk, 'tenant': connection.schema_name}, salt=CHALLENGE_SALT)


def user_from_challenge(challenge):
    try:
        data = signing.loads(challenge, salt=CHALLENGE_SALT, max_age=CHALLENGE_SECONDS)
    except signing.BadSignature as exc:  # includes expired
        raise ValidationError('This sign-in has expired. Enter your password again.') from exc
    if data.get('tenant') != connection.schema_name:
        raise ValidationError('This sign-in has expired. Enter your password again.')
    user = User.objects.filter(pk=data.get('user'), is_active=True).first()
    if user is None:
        raise ValidationError('This sign-in has expired. Enter your password again.')
    return user


# ---- Managing it ----


@transaction.atomic
def new_recovery_codes(user, code):
    if not verify(user, code):
        raise ValidationError({'code': 'Enter a current code from your authenticator app.'})
    codes = _new_recovery_codes()
    TwoFactor.objects.filter(user=user).update(recovery_codes=[_hash(c) for c in codes])
    record('two_factor_recovery_codes_replaced', Category.SECURITY, actor=user)
    return codes


def disable(user, *, password, code):
    if required_for(user):
        raise ValidationError('Two-factor sign-in is required for your role and can\'t be turned off.')
    if not user.check_password(password):
        raise ValidationError({'password': 'Incorrect password.'})
    if not verify(user, code):
        raise ValidationError({'code': 'Enter a current code from your authenticator app.'})
    TwoFactor.objects.filter(user=user).delete()
    record('two_factor_disabled', Category.SECURITY, actor=user)


def reset(user, *, by=None):
    '''Lost phone and recovery codes: remove it, so the person sets it up again at next sign-in.'''
    from . import services

    TwoFactor.objects.filter(user=user).delete()
    services.revoke_all_sessions(user)
    record(
        'two_factor_reset', Category.SECURITY, resource=user,
        metadata={'user_id': user.pk, 'by': getattr(by, 'email', 'platform command')},
    )  # fmt: skip
