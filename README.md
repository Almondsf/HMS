# HMS: Hospital Management System API

A multi-hospital Django REST backend for running clinics and hospitals: patient registration, visits, consultations (SOAP notes), prescriptions, laboratory and pharmacy, with role-based access and a full audit trail. One deployment serves many hospitals, and each hospital's data lives in its own isolated database schema.

## Modules

| App | What it covers |
|---|---|
| `authentication` | Email login with JWT, roles, account lockout, logout, password change, `/me` |
| `profiles` | Patient and staff profiles (doctor, lab tech, pharmacist, receptionist) |
| `clinical` | Visits, consultations, prescriptions, pharmacy prescription queue |
| `lab` | Test catalogue, orders (from consultations or walk-in), results |
| `pharmacy` | Drug stock, dispensing against prescriptions |
| `audit` | Append-only audit trail, security events, domain events |
| `tenants` | Hospitals, their addresses, provisioning, the platform site |

## Quick start

**With Docker** (Postgres included):

```bash
docker compose up
docker compose exec web python manage.py create_hospital --name "Demo Hospital" --schema demo --admin-email you@example.com
```

**Without Docker** (needs Python 3.12 and a running PostgreSQL):

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env             # then set your DB_* values
python manage.py migrate
python manage.py setup_platform
python manage.py create_hospital --name "Demo Hospital" --schema demo --admin-email you@example.com
python manage.py runserver
```

`create_hospital` prints a one-time password for the hospital's admin. The hospital is then live at **http://demo.localhost:8000**: API docs at `/api/docs/`, admin at `/admin/`. Browsers and curl resolve `*.localhost` to your machine.

The hospital admin creates staff through `/api/create-profile/<role>/`. Patients are registered by an admin or receptionist.

## Multi-tenancy

Each hospital is a **tenant** with its own Postgres schema ([django-tenants](https://django-tenants.readthedocs.io/)). Requests are routed by hostname:

| Address | Serves |
|---|---|
| `<hospital>.<TENANT_BASE_DOMAIN>` | That hospital's API, admin and docs ([hms/urls.py](hms/urls.py)) |
| `PLATFORM_DOMAINS` | The platform: operator login and the admin for hospitals ([hms/urls_public.py](hms/urls_public.py)) |
| anything else | `404`, except `/api/health/`, which answers on any host |

- **Isolation:** users, patients and all records live in the hospital's schema. One hospital's queries cannot reach another's tables.
- **Tokens are bound to their hospital:** each JWT carries a `tenant` claim and is rejected at any other hospital or at the platform. Without this, user #5's token from one hospital would authenticate as a different user #5 elsewhere ([authentication/tokens.py](authentication/tokens.py)).
- **Suspension:** setting a hospital's `is_active` to false blocks all access to it (403) without touching its data.
- **Adding apps:** shared (platform) apps go in `SHARED_APPS`, per-hospital apps in `TENANT_APPS` ([hms/settings/base.py](hms/settings/base.py)). `migrate` migrates every schema.
- **Code outside a request** (commands, jobs) must pick a hospital first:
  ```python
  from django_tenants.utils import tenant_context

  with tenant_context(hospital):
      ...
  ```

**Platform API** (on a platform domain, for platform superusers only):

| Endpoint | Purpose |
|---|---|
| `POST /api/platform/hospitals/` | Provision a hospital. Takes `name`, `schema_name`, `plan` and `admin_*` fields; returns the admin's one-time password if none was given |
| `GET /api/platform/hospitals/` | List hospitals with their domains, plans and status |
| `PATCH /api/platform/hospitals/<id>/` | Change plan or settings; `is_active: false` suspends the hospital |

**Hospital settings:** `GET/PATCH /api/hospital/` on the hospital's own site. Everyone signed in can read them; admins edit:
- `name`, `contact_email`, `phone`, `address`
- `timezone`: API timestamps are shown in it
- `currency`
- `mrn_prefix`: prefix for patient record numbers

The response also lists the `features` the hospital's plan includes, so frontends can show only the modules available.

**Plans and modules** ([tenants/features.py](tenants/features.py)):

| Plan | Modules |
|---|---|
| Basic | Front desk & consultations, Pharmacy |
| Pro | + Laboratory |
| Enterprise | All modules |

Endpoints of a module the plan doesn't include return 403 with an explanation.

**Management commands**

| Command | Purpose |
|---|---|
| `setup_platform [domain ...]` | Register the platform site and its domains. Idempotent; run on every deploy |
| `create_hospital --name --schema --admin-email [--domain --plan]` | Provision a hospital: schema, address and first admin |
| `adopt_legacy_data --schema <hospital> [--force]` | One-time upgrade: copy a pre-multi-tenancy database (data in `public`) into a hospital |

## Roles and access

Within a hospital, access is enforced on every endpoint with `authentication.permissions.allow_roles`. Superusers can do everything in their own hospital.

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
def notify_doctor(event): ...  # event.name, event.resource, event.payload
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

1. **Domains:**
   - Choose a base domain for hospitals, e.g. `hms.app`.
   - Add a wildcard custom domain (`*.hms.app`) to the Render service.
   - Point a wildcard DNS record at Render.
2. **Environment variables:**
   - `DATABASE_URL` and `SECRET_KEY`
   - `TENANT_BASE_DOMAIN=hms.app`
   - `PLATFORM_DOMAINS`: e.g. `hms.app`. Render's own hostname is added automatically.
   - `CORS_ALLOWED_ORIGINS` or `CORS_ALLOWED_ORIGIN_REGEXES` for your frontends
3. **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py setup_platform`
4. **Start command:** `gunicorn hms.wsgi --access-logfile -`
5. **Health check path:** `/api/health/`
6. **Create hospitals** from the Render shell: `python manage.py create_hospital ...`

On Render, `manage.py` automatically uses production settings. Elsewhere, set `DJANGO_SETTINGS_MODULE=hms.settings.prod`. A production [Dockerfile](Dockerfile) is also provided: it runs as a non-root user and includes a health check.

### Upgrading a single-hospital deployment

Before multi-tenancy, all data lived in the `public` schema. To move it into a hospital:

1. Back up the database.
2. Deploy. The build command migrates the shared schema and registers the platform.
3. In the Render shell, create the hospital:
   `python manage.py create_hospital --name "..." --schema main --admin-email ...`
4. Then copy the data:
   `python manage.py adopt_legacy_data --schema main --force`

`--force` is needed because the new hospital already contains its setup admin. The copy replaces it with your existing users, who keep their passwords. The source tables in `public` are left untouched and can be dropped once you've verified the hospital.
