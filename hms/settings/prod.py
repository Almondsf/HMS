"""
Production. Refuses to start without the settings that keep it safe,
rather than silently falling back to insecure defaults.
"""

from decouple import config
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, PLATFORM_DOMAINS, SECRET_KEY, TENANT_BASE_DOMAIN

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith('django-insecure'):
    raise ImproperlyConfigured('SECRET_KEY must be set to a strong random value in production.')

# Hosts: the platform's own domains, every hospital subdomain, Render's
# service hostname, plus anything extra in ALLOWED_HOSTS
RENDER_EXTERNAL_HOSTNAME = config('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME:
    PLATFORM_DOMAINS = [*PLATFORM_DOMAINS, RENDER_EXTERNAL_HOSTNAME]
ALLOWED_HOSTS = [*ALLOWED_HOSTS, *PLATFORM_DOMAINS]
if TENANT_BASE_DOMAIN != 'localhost':
    ALLOWED_HOSTS.append(f'.{TENANT_BASE_DOMAIN}')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS must list the real hostnames (no "*") in production.')

# Render/most PaaS terminate TLS at a proxy that sets X-Forwarded-For
AUDIT_TRUST_X_FORWARDED_FOR = config('AUDIT_TRUST_X_FORWARDED_FOR', default=True, cast=bool)

# HTTPS everywhere (TLS terminates at the platform's proxy)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS: start at 30 days; raise to a year once HTTPS is confirmed stable
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=60 * 60 * 24 * 30, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)

# Preload is hard to undo; opt in deliberately once on a permanent domain
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)
if not SECURE_HSTS_PRELOAD:
    SILENCED_SYSTEM_CHECKS = ['security.W021']
