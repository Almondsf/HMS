"""Local development: debug on, permissive defaults, nothing required in .env."""

from decouple import config

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, CORS_ALLOWED_ORIGIN_REGEXES, CORS_ALLOWED_ORIGINS, PLATFORM_DOMAINS, SECRET_KEY

DEBUG = True

SECRET_KEY = SECRET_KEY or 'django-insecure-dev-only-never-use-in-production'
# '.localhost' lets hospitals run at e.g. http://stlukes.localhost:8000
ALLOWED_HOSTS = ALLOWED_HOSTS or ['localhost', '.localhost', '127.0.0.1', '[::1]']
PLATFORM_DOMAINS = PLATFORM_DOMAINS or ['localhost', '127.0.0.1']
CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS or [
    'http://localhost:3000',  # React / Next.js
    'http://localhost:5173',  # Vite
]
# The frontend runs per hospital at http://<hospital>.localhost:5173
CORS_ALLOWED_ORIGIN_REGEXES = CORS_ALLOWED_ORIGIN_REGEXES or [r'^http://([a-z0-9-]+\.)?localhost:(3000|5173)$']

API_DOCS_PUBLIC = True

# Human-readable logs locally unless LOG_FORMAT says otherwise
LOGGING['handlers']['console']['formatter'] = config('LOG_FORMAT', default='text')  # noqa: F405
