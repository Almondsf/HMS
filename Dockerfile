# Production image: the API and the web app in one service.
# Local development: see docker-compose.yml.

# ---- 1. Build the web app ----
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. The Django service ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# Django serves the built app at each hospital's address (hms/spa.py)
COPY --from=frontend /frontend/dist ./frontend/dist

# Static files are baked into the image (served by WhiteNoise); no DB needed
RUN DJANGO_SETTINGS_MODULE=hms.settings.dev python manage.py collectstatic --noinput

# Never run as root
RUN useradd --create-home --uid 1000 hms && chown -R hms /app
USER hms

ENV DJANGO_SETTINGS_MODULE=hms.settings.prod
# Hosting platforms (Render) say which port to use via PORT
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/api/health/')" || exit 1

CMD ["sh", "-c", "gunicorn hms.wsgi --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-3} --access-logfile -"]
