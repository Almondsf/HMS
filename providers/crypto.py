'''Encrypting provider secrets at rest (Fernet: AES with an integrity check).'''

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def generate_key():
    return Fernet.generate_key().decode()


def _fernet():
    key = settings.PROVIDER_ENCRYPTION_KEY
    if not key:
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                'Set PROVIDER_ENCRYPTION_KEY to store provider keys. Generate one with: '
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        # Development only: a key derived from SECRET_KEY
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt(values):
    return _fernet().encrypt(json.dumps(values).encode()).decode() if values else ''


def decrypt(token):
    if not token:
        return {}
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken as exc:
        raise ImproperlyConfigured(
            'Stored provider keys cannot be decrypted: PROVIDER_ENCRYPTION_KEY has changed. Re-enter the keys.'
        ) from exc


def mask(value):
    value = str(value or '')
    return f'••••{value[-4:]}' if len(value) > 4 else '••••' if value else ''
