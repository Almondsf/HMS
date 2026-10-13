"""Local development: debug on, permissive defaults, nothing required in .env."""

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, SECRET_KEY

DEBUG = True

SECRET_KEY = SECRET_KEY or 'django-insecure-dev-only-never-use-in-production'
ALLOWED_HOSTS = ALLOWED_HOSTS or ['localhost', '127.0.0.1', '[::1]']
CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS or [
    'http://localhost:3000',  # React / Next.js
    'http://localhost:5173',  # Vite
]

API_DOCS_PUBLIC = True
