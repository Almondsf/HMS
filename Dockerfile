# Production image. Local development: see docker-compose.yml.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Static files are baked into the image (served by WhiteNoise); no DB needed
RUN DJANGO_SETTINGS_MODULE=hms.settings.dev python manage.py collectstatic --noinput

# Never run as root
RUN useradd --create-home --uid 1000 hms && chown -R hms /app
USER hms

ENV DJANGO_SETTINGS_MODULE=hms.settings.prod
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" || exit 1

CMD ["gunicorn", "hms.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
