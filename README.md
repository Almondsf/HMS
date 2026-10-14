# HMS: Hospital Management System API

A multi-hospital Django REST backend for running clinics and hospitals: patient registration, visits, consultations (SOAP notes), prescriptions, laboratory and pharmacy, with role-based access and a full audit trail. One deployment serves many hospitals, and each hospital's data lives in its own isolated database schema.

## Modules

| App | What it covers |
|---|---|
| `authentication` | Email login with JWT, roles, account lockout, logout, password change, `/me` |
| `profiles` | Patient registry with medical record numbers, staff directory (doctor, nurse, lab tech, pharmacist, receptionist), departments |
| `clinical` | Visits and the patient queue, consultations, prescriptions, pharmacy prescription queue |
| `scheduling` | Appointments: booking without double-booking, check-in, no-shows |
| `lab` | Test catalogue, orders (from consultations or walk-in), results |
| `pharmacy` | Drug stock, dispensing against prescriptions |
| `audit` | Append-only audit trail, security events, domain events |
| `tenants` | Hospitals, their addresses, provisioning, the platform site |
| `terminology` | Shared reference data: ICD-10 diagnosis codes |
| `billing` | Tariff, invoices built automatically from care, payments, receipts, daily cash summary |
| `insurance` | HMO / NHIA providers, patient cover, claims and insurer payments |

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

The hospital admin creates staff through `/api/v1/create-profile/<role>/`. Patients are registered by an admin or receptionist.

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
| `POST /api/v1/platform/hospitals/` | Provision a hospital. Takes `name`, `schema_name`, `plan` and `admin_*` fields; returns the admin's one-time password if none was given |
| `GET /api/v1/platform/hospitals/` | List hospitals with their domains, plans and status |
| `PATCH /api/v1/platform/hospitals/<id>/` | Change plan or settings; `is_active: false` suspends the hospital |

**Hospital settings:** `GET/PATCH /api/v1/hospital/` on the hospital's own site. Everyone signed in can read them; admins edit:
- `name`, `contact_email`, `phone`, `address`
- `timezone`: API timestamps are shown in it
- `currency`
- `mrn_prefix`: prefix for patient record numbers

The response also lists the `features` the hospital's plan includes, so frontends can show only the modules available.

**Plans and modules** ([tenants/features.py](tenants/features.py)):

| Plan | Modules |
|---|---|
| Basic | Front desk & consultations, Pharmacy, Billing |
| Pro | + Laboratory, HMO / insurance claims |
| Enterprise | All modules |

Endpoints of a module the plan doesn't include return 403 with an explanation.

**Management commands**

| Command | Purpose |
|---|---|
| `setup_platform [domain ...]` | Register the platform site and its domains. Idempotent; run on every deploy |
| `create_hospital --name --schema --admin-email [--domain --plan]` | Provision a hospital: schema, address and first admin |
| `adopt_legacy_data --schema <hospital> [--force]` | One-time upgrade: copy a pre-multi-tenancy database (data in `public`) into a hospital |
| `load_icd10 <file.csv> [--deactivate-missing]` | Load or update ICD-10 codes (`code,title` columns) for all hospitals |

## Roles and access

Within a hospital, access is enforced on every endpoint with `authentication.permissions.allow_roles`. Superusers can do everything in their own hospital.

| Resource | Read | Write |
|---|---|---|
| Patients (`/api/v1/patients/`) | doctor, nurse, lab tech, pharmacist · patient: own | admin, receptionist |
| Staff directory (`/api/v1/staff/`) | all staff | admin (deactivate / activate) |
| Departments | all staff | admin |
| Register staff (`/api/v1/create-profile/<role>/`) | | admin |
| Visits | admin, receptionist, nurse: all · doctor, patient: own | admin, receptionist |
| Consultations | admin · doctor, patient: own | assigned doctor |
| Prescriptions queue | pharmacist, admin · doctor, patient: own | (created with consultations) |
| Lab catalogue | all staff | admin, lab tech |
| Lab orders / results | admin, lab tech · doctor: own patients | doctor, lab tech (orders) · lab tech (results) |
| Drugs | doctor, nurse, pharmacist, admin | pharmacist, admin |
| Dispensing | admin, pharmacist | pharmacist |
| Audit log | admin | (nobody) |

Receptionists see visits without clinical notes. Clinical and dispensing records can't be deleted through the API.

### Patients and staff

- **Medical record numbers (MRN):**
  - Assigned at registration as `<prefix>-000123`, using the hospital's `mrn_prefix`.
  - Numbers come from a locked per-hospital counter, so concurrent registrations never collide.
  - To keep a patient's existing paper record number, send it as `mrn`; generated numbers skip it.
  - An MRN never changes.
- **Patients without email or password:** a patient can be registered with neither (they simply can't sign in). Staff always need both.
- **Search:** `GET /api/v1/patients/?search=ada obi` matches every word against name, MRN, phone and email.
- **Staff:**
  - `GET /api/v1/staff/?role=doctor&department=<id>` lists staff, e.g. for assigning visits.
  - `POST /api/v1/staff/<id>/deactivate/` disables an account and signs it out everywhere. Accounts are never deleted, and an admin can't deactivate their own account.
  - Inactive doctors can't be assigned new visits.

### Appointments and the queue

```
book appointment ──check-in──▶ visit: waiting ──start──▶ in consultation ──complete──▶ completed
        │                         │ (walk-ins start here)
        └─ cancel / no-show       └─ cancel (front desk, before being seen)
```

- **Booking:** `POST /api/v1/appointments/` takes a patient, doctor, `starts_at` and `duration_minutes`.
  - A doctor can't be double-booked, and neither can a patient.
  - Bookings for the same doctor or patient are processed one at a time, so two simultaneous requests can't both take the same slot.
  - Reschedule with a `PATCH` to `starts_at` or `duration_minutes`.
- **Check-in:** `POST /api/v1/appointments/<id>/check-in/`, only on the day, opens a visit in the doctor's queue.
- **Queue:** `GET /api/v1/queue/` shows today's queue. The patient in the room is listed first, then those waiting with `position` and `waiting_minutes`. Doctors see their own queue; others can filter with `?doctor=<id>`.
- **Visit status** only changes through actions:
  - `POST /api/v1/visits/<id>/start/` and `/complete/`, by the assigned doctor
  - `/cancel/`, by the front desk while the patient is still waiting
  - Recording a consultation starts a waiting visit automatically.

### Triage and vital signs

- **Vitals:** nurses record vital signs for any visit, doctors for their own patients, with `POST /api/v1/vitals/`.
  - Every measurement is optional.
  - Values outside physiological limits are rejected as typos.
  - Each set comes back with `bmi`, `flags` (e.g. `fever`, `low oxygen saturation`) and `is_critical`.
  - Critical readings publish `clinical.critical_vitals`.
  - Readings are never edited; to correct one, record a new set.
  - `?patient=<id>` returns a patient's history for charting.
  - Thresholds are in [clinical/vitals.py](clinical/vitals.py). Have them reviewed by your clinical lead.
- **Triage:** `POST /api/v1/visits/<id>/triage/` sets `triage_level` to `emergency`, `urgent`, `standard` or `non_urgent`.
  - The queue orders waiting patients by priority, then arrival.
  - Emergencies publish `clinical.emergency_arrival`.

### Diagnoses (ICD-10)

- **Codes:** ICD-10 codes are shared by every hospital.
  - A starter set of about 45 codes common in West African care is loaded automatically.
  - For production, load a complete list with `load_icd10`. Check the licensing terms of the list you choose (e.g. WHO ICD-10).
  - Look codes up with `GET /api/v1/icd10/?search=malaria`. A code also matches without its dot (`b509`).
- **Recording diagnoses:** doctors add them inline when creating a consultation (`diagnoses: [...]`), or later with `POST /api/v1/diagnoses/`.
  - Each has a `kind` (`primary` or `secondary`) and a `certainty` (`provisional`, `confirmed` or `ruled_out`).
  - A consultation can have only one active primary diagnosis.
  - When no code fits, a free-text `description` can be used instead.
  - Diagnoses are never deleted; rule them out instead.

### Billing

- **Tariff:** admins configure `ServiceItem`s at `/api/v1/billing/services/`. An item's `charge_on` makes it automatic (`visit_opened`, e.g. a card fee, or `consultation_recorded`); otherwise the cashier adds it by hand. Lab tests are priced by their `cost`, drugs by `unit_price`.
- **Automatic charges:** each visit's draft invoice collects charges as care happens: visit and consultation fees, lab tests ordered and drugs dispensed. Walk-in lab patients get their own invoice.
  - Charges run **inside the same transaction** as the clinical action: a service is never recorded without its charge, and a billing failure rolls the action back.
  - Each source is charged once.
  - An item with no price is charged at 0 and flagged `needs_price`. Care is never blocked, but the invoice can't be issued until the line is priced.
- **Invoice flow:** `draft → issued → paid`, or `void`.
  - Cashiers add lines, price flagged lines, void lines (with a reason) and issue the invoice.
  - Admins apply discounts (with a reason) and void invoices that have no payments.
  - After issue, the lines are fixed.
- **Payments:** `POST /api/v1/billing/payments/` by cashiers, admins or the front desk.
  - The invoice is locked while a payment is recorded, so a double submission can't overpay; payments can never exceed the balance.
  - An issued invoice becomes `paid` when its balance reaches zero.
  - Admins void payments recorded in error, which re-opens the invoice.
  - `GET /api/v1/billing/payments/<id>/receipt/` returns everything needed to print a receipt.
- **End of day:** `GET /api/v1/billing/summary/?date=` gives money taken by payment method and cashier, charges by category, and the number of outstanding invoices.
- **Roles:** a new `cashier` role, created at `/api/v1/create-profile/cashiers/`. Patients can see their own invoices and payments.

### HMO / insurance (Pro plan)

- **Setup:** admins register the providers the hospital accepts at `/api/v1/insurance/providers/` (HMO, NHIA, private insurer, corporate retainer). Each provider has a default coverage % and may require pre-authorisation codes. The front desk records patients' cover (member number, validity dates, optional coverage %) at `/api/v1/insurance/coverages/`.
- **Claims:** `POST /api/v1/insurance/claims/` on an issued invoice. The flow is `draft → submit → respond → pay`, with each step an action on the claim.
  - While a claim is open, its amount is set aside: the invoice shows `pending_insurance`, and the patient pays only `patient_due`.
  - A rejection, or the shortfall of a partial approval or short payment, goes back to the patient.
  - The insurer's payment is recorded as an `insurance` payment, so the invoice settles normally. Insurance payments can only be made through claims.
- **Checks:** the cover must belong to the patient and be valid on the date of service, providers that require it need an authorisation code, and an invoice can have only one open claim.
- **Claim document:** `GET /api/v1/insurance/claims/<id>/document/` returns the member details, ICD-10 diagnoses and itemised charges.
- **Chasing payment:** `GET /api/v1/insurance/claims/outstanding/` shows what each insurer still owes.

## API conventions

- **Versioned:** every endpoint lives under `/api/v1/`.
  - Older `/api/...` paths still work, but their responses carry `Deprecation: true` and a `Link` header pointing to the `/api/v1/` address.
  - Breaking changes will go to `/api/v2/`.
- **Docs and health** are not versioned: `/api/docs/`, `/api/redoc/`, `/api/schema.json` and `/api/health/`.
- **Pagination:** `?page=N`. `?page_size=N` sets the page size, up to 100.
- **Filtering and sorting:** query parameters, e.g. `/api/v1/visits/?status=in_progress&date_from=2026-10-01&ordering=-visit_date`. Each endpoint's filters are listed in the API docs. Some useful ones:
  - `/api/v1/prescriptions/?pending=true`: the pharmacy's queue
  - `/api/v1/pharmacy/drugs/?low_stock=true`
  - `/api/v1/lab/test-orders/?status=pending`
- **Errors are always JSON:**
  - validation: `{"field": ["message"]}`
  - other errors: `{"detail": "message"}`
  - server errors also include a `request_id` to quote to support

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
- **Find everyone who accessed a patient:** `GET /api/v1/audit/events/?patient=<id>`. Other filters: `category`, `action`, `actor_id`, `resource_type`, `resource_id`, `request_id`, `since`, `until`.
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
