# HMS: Hospital Management System API

A Django REST backend for running a clinic or hospital: patient registration, visits, consultations (SOAP notes), prescriptions, laboratory and pharmacy, with role-based access and a full audit trail.

## Modules

| App | What it covers |
|---|---|
| `authentication` | Email login with JWT, roles, account lockout, logout, password change, `/me` |
| `profiles` | Patient and staff profiles (doctor, lab tech, pharmacist, receptionist) |
| `clinical` | Visits, consultations, prescriptions, pharmacy prescription queue |
| `lab` | Test catalogue, orders (from consultations or walk-in), results |
| `pharmacy` | Drug stock, dispensing against prescriptions |
| `audit` | Append-only audit trail, security events, domain events |

## Quick start

**With Docker** (Postgres included):

```bash
docker compose up
docker compose exec web python manage.py createsuperuser
```

**Without Docker** (needs Python 3.12 and a running PostgreSQL):

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env             # then set your DB_* values
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API docs: http://localhost:8000/api/docs/. Admin: http://localhost:8000/admin/.

The first superuser is the hospital admin. Staff accounts are then created by an admin through `/api/create-profile/<role>/`, and patients by an admin or receptionist.

## Roles and access

Enforced on every endpoint with `authentication.permissions.allow_roles`. Superusers can do everything.

| Resource | Read | Write |
|---|---|---|
| Register patients | | admin, receptionist |
| Register staff | | admin |
| Visits | admin, receptionist, nurse: all · doctor, patient: own | admin, receptionist |
| Consultations | admin · doctor, patient: own | assigned doctor |
| Prescriptions queue | pharmacist, admin · doctor, patient: own | (created with consultations) |
| Lab catalogue | all staff | admin, lab tech |
| Lab orders / results | admin, lab tech · doctor: own patients | doctor, lab tech (orders) · lab tech (results) |
| Drugs | doctor, nurse, pharmacist, admin | pharmacist, admin |
| Dispensing | admin, pharmacist | pharmacist |
| Audit log | admin | (nobody) |

Receptionists see visits without clinical notes. Clinical and dispensing records can't be deleted through the API.

## Architecture

```
request → view (permissions, scoping) → serializer (input shape) → service (business rules) → models
                                                                          └→ audit events / domain events
```

- **Services hold the business rules** (`clinical/services.py`, `lab/services.py`, `pharmacy/services.py`). They raise plain Django `ValidationError`/`PermissionDenied`, so they work the same from the API, admin, shell or background jobs. `helpers/api.py` turns those into 400/403 responses (and `ProtectedError` into 409).
- **Dispensing is concurrency-safe:** drug and prescription rows are locked for the whole transaction, so stock and prescribed quantities can't be oversold.
- **Medical records protect their history:** foreign keys use `PROTECT`, not cascading deletes. Deactivate users instead of deleting them.

### Audit trail

Every change to a registered model (via the API, admin or shell), every read of patient data, and every security event is written to `audit.AuditEvent`. Each event stores the actor, role, resource, patient, field-level changes, IP, user agent and request id.

- **Append-only:** updates and deletes are refused by the model and by a Postgres trigger.
- **Find everyone who accessed a patient:** `GET /api/audit/events/?patient=<id>`. Other filters: `category`, `action`, `actor_id`, `resource_type`, `resource_id`, `request_id`, `since`, `until`.
- **Registering a model:** done in its app's `AppConfig.ready()`:
  ```python
  registry.register(Visit, patient=lambda visit: visit.patient_id)
  ```
- **Logging reads on a viewset:** add `AuditedReadMixin`.
- **Bulk updates must be recorded by hand:** `queryset.update()` bypasses model signals, so call `audit.recorder.record(...)` yourself (see `pharmacy.services`).

### Domain events

Business events are published from services and delivered **after the transaction commits**:

```python
from audit import events

@events.subscribe('lab.result_completed')
def notify_doctor(event):
    ...  # event.name, event.resource, event.payload
```

Published today: `clinical.visit_opened`, `clinical.consultation_recorded`, `lab.order_placed`, `lab.result_completed`, `lab.order_completed`, `pharmacy.dispensed`, `pharmacy.stock_low`. Each one is also stored in the audit trail.

### Logging

Logs are JSON lines in production and readable text locally (`LOG_FORMAT`). Every line carries the request id, which is also returned in the `X-Request-ID` response header. Quote it in support tickets to find the matching logs and audit events.

## Settings

| Module | Used by |
|---|---|
| `hms.settings.dev` | `manage.py` locally (default) |
| `hms.settings.prod` | `wsgi`/`asgi`, and `manage.py` on Render |
| `hms.settings.test` | pytest |

Production refuses to start without a real `SECRET_KEY` and explicit `ALLOWED_HOSTS`. It forces HTTPS, sends HSTS headers and uses secure cookies. All variables are documented in [.env.example](.env.example).

## Tests and quality checks

```bash
pytest                       # full suite
pytest --cov                 # with coverage
ruff check . && ruff format --check .
pip-audit -r requirements.txt
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs on every push and pull request:
- lint and formatting checks
- tests on Postgres 16, with an 85% coverage floor
- a migration drift check
- a dependency vulnerability audit

Optional local hooks: `pip install pre-commit && pre-commit install`.

## Deploying (Render)

1. Set these environment variables:
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `CORS_ALLOWED_ORIGINS`: your frontend's URL
   - optionally `ALLOWED_HOSTS` for custom domains
2. **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
3. **Start command:** `gunicorn hms.wsgi --access-logfile -`
4. Point the health check at `/api/health/`.

On Render, `manage.py` automatically uses production settings. Elsewhere, set `DJANGO_SETTINGS_MODULE=hms.settings.prod`. A production [Dockerfile](Dockerfile) is also provided: it runs as a non-root user and includes a health check.
