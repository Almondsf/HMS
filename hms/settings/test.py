"""Test runs: fast hashing, no throttling limits, no static manifest needed."""

from .dev import *  # noqa: F401,F403
from .dev import REST_FRAMEWORK

# Hashing strength is irrelevant in tests and dominates their runtime
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {
        'anon': '10000/min',
        'user': '10000/min',
        'login': '10000/min',
        'password_reset': '10000/min',
        'signup': '10000/min',
    },
}

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# Create signed-up hospitals in the request's thread, so tests can see them
SIGNUP_PROVISION_IN_BACKGROUND = False
SMS_SEND_IN_BACKGROUND = False
SMS_BACKEND = ''  # tests switch it on where needed

LOGGING['root']['level'] = 'WARNING'  # noqa: F405
