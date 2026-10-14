"""
Settings shared by every environment.

Environment modules (dev, prod, test) import everything from here and
override what differs. Values are read from environment variables first,
then from a local .env file (python-decouple).
"""

from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='')
DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())


# Application definition

# Multi-tenancy: one Postgres schema per hospital (django-tenants).
# SHARED_APPS live in the public schema (the platform); TENANT_APPS are
# created inside every hospital's schema. Apps in both exist in each.

SHARED_APPS = [
    'django_tenants',
    'tenants',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'drf_yasg',
    # Platform operators and platform-level audit trail
    'authentication',
    'rest_framework_simplejwt.token_blacklist',
    'audit',
    # Shared reference data (ICD-10 codes)
    'terminology',
]

TENANT_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'authentication',
    'rest_framework_simplejwt.token_blacklist',
    'audit',
    'profiles',
    'clinical',
    'lab',
    'pharmacy',
    'scheduling',
    'billing',
]

INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = 'tenants.Hospital'
TENANT_DOMAIN_MODEL = 'tenants.Domain'
DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

# Hospitals get <subdomain>.<TENANT_BASE_DOMAIN>, e.g. stlukes.hms.app
TENANT_BASE_DOMAIN = config('TENANT_BASE_DOMAIN', default='localhost')
# Hostnames serving the platform itself (public schema); see setup_platform
PLATFORM_DOMAINS = config('PLATFORM_DOMAINS', default='', cast=Csv())

MIDDLEWARE = [
    'tenants.middleware.HealthCheckMiddleware',
    'tenants.middleware.HospitalMiddleware',  # selects the hospital schema; must precede anything using the DB
    'tenants.middleware.HospitalTimezoneMiddleware',
    'helpers.middleware.LegacyApiPathMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'audit.context.AuditContextMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hms.urls'  # hospital sites
PUBLIC_SCHEMA_URLCONF = 'hms.urls_public'  # platform site

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hms.wsgi.application'


# Database: DATABASE_URL (hosting platforms) or individual DB_* variables

DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL, engine='django_tenants.postgresql_backend', conn_max_age=600, conn_health_checks=True
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django_tenants.postgresql_backend',
            'NAME': config('DB_NAME', default='hms'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'authentication.User'


# API

REST_FRAMEWORK = {
    # Tokens are bound to the hospital that issued them (see authentication/tokens.py)
    'DEFAULT_AUTHENTICATION_CLASSES': ('authentication.tokens.TenantJWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'helpers.api.StandardPagination',
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ],
    'PAGE_SIZE': 10,
    'EXCEPTION_HANDLER': 'helpers.api.api_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('THROTTLE_ANON', default='60/min'),
        'user': config('THROTTLE_USER', default='2000/hour'),
        'login': config('THROTTLE_LOGIN', default='10/min'),
    },
}

SIMPLE_JWT = {
    # Short-lived access tokens: a leaked token is only useful briefly
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_MINUTES', default=15, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# API docs are open in development and staff-only (admin session) in production
API_DOCS_PUBLIC = config('API_DOCS_PUBLIC', default=False, cast=bool)
SWAGGER_USE_COMPAT_RENDERERS = False


# Authentication & passwords

# Argon2 first; existing PBKDF2 hashes still verify and are upgraded on next login
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Account lockout after repeated failed logins
LOGIN_MAX_FAILED_ATTEMPTS = config('LOGIN_MAX_FAILED_ATTEMPTS', default=5, cast=int)
LOGIN_LOCKOUT_MINUTES = config('LOGIN_LOCKOUT_MINUTES', default=15, cast=int)

# Obscure the admin path in production (e.g. ADMIN_URL=staff-portal-8f3a/)
ADMIN_URL = config('ADMIN_URL', default='admin/')


# CORS: browser frontends allowed to call the API

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
# e.g. ^https://[a-z0-9-]+\.hms\.app$ to allow every hospital's frontend
CORS_ALLOWED_ORIGIN_REGEXES = config('CORS_ALLOWED_ORIGIN_REGEXES', default='', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())


# Security headers that are safe in every environment

X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True


# Cache keys are prefixed with the hospital schema, so throttling and any
# cached data never leak between hospitals
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'KEY_FUNCTION': 'django_tenants.cache.make_key',
        'REVERSE_KEY_FUNCTION': 'django_tenants.cache.reverse_key',
    }
}


# Audit & logging

# Behind a proxy/load balancer (Render, nginx) the client IP is in X-Forwarded-For.
# Only trust it when such a proxy is guaranteed to overwrite the header.
AUDIT_TRUST_X_FORWARDED_FOR = config('AUDIT_TRUST_X_FORWARDED_FOR', default=False, cast=bool)

LOG_LEVEL = config('LOG_LEVEL', default='INFO')
LOG_FORMAT = config('LOG_FORMAT', default='json')  # 'json' or 'text'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id': {'()': 'helpers.logging.RequestIdFilter'},
    },
    'formatters': {
        'json': {'()': 'helpers.logging.JsonFormatter'},
        'text': {'format': '%(asctime)s %(levelname)s [%(name)s] [%(tenant)s] [%(request_id)s] %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['request_id'],
            'formatter': LOG_FORMAT,
        },
    },
    'root': {'handlers': ['console'], 'level': LOG_LEVEL},
    'loggers': {
        # Replace Django's own console handler so lines aren't printed twice
        'django': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'django.db.backends': {'level': 'WARNING'},
    },
}


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static & media files

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').is_dir() else []

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
