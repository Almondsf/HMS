# HMS: Hospital Management System API

A multi-hospital Django REST backend for running clinics and hospitals: patient registration, visits, consultations (SOAP notes), prescriptions, laboratory and pharmacy, with role-based access and a full audit trail. One deployment serves many hospitals, and each hospital's data lives in its own isolated database schema.

**New here?** Start with the [product and system overview](docs/PRODUCT_OVERVIEW.md) (what the app does and how it's built) and the [user stories](docs/USER_STORIES.md) (what each kind of user needs). To run or host it, see [running and hosting](docs/RUNNING_AND_HOSTING.md). The [launch plan](docs/LAUNCH_PLAN.md) lists the next steps. This README is the feature and API reference.

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
| `reports` | Clinical, financial, pharmacy and lab management reports |

## Quick start

The full guide, including demo data, the web app, hosting on Render and troubleshooting, is [docs/RUNNING_AND_HOSTING.md](docs/RUNNING_AND_HOSTING.md).

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

## Frontend

The web app is in [frontend/](frontend/). It uses React 19, TypeScript, Vite, Tailwind CSS (white and sky blue, defined as `brand-*` colours in [src/index.css](frontend/src/index.css)), React Router and TanStack Query.

```bash
cd frontend
npm install
npm run dev        # then open http://<hospital>.localhost:5173, e.g. http://main.localhost:5173
npm run build      # type-check + production build into dist/
```

- **Which hospital:** the app works out the hospital from its own address (`main.localhost:5173` means hospital `main`), and talks to that hospital's API at `http://main.localhost:8000` by default. In production, set `VITE_TENANT_BASE_DOMAIN` and `VITE_API_URL` (see [frontend/.env.example](frontend/.env.example)).
- **Sessions:** nothing is kept in browser storage. The refresh token lives in an `httpOnly` cookie, so page scripts can't read or steal it, and it's limited to `/api/v1/auth/`. The short-lived access token is held in memory, and the session is restored from the cookie after a reload. Requests that need a refresh at the same moment share one refresh, because refresh tokens rotate. Signing out revokes the token and clears the cookie. API clients that send the refresh token in the JSON body work as before; browsers opt into cookies with the `X-HMS-Auth-Mode: cookie` header, which also guards against CSRF.
- **Hosting:** `dist/` is static files, so it can be served from any static host or CDN.

**Screens by role** (the sidebar shows only what the role and the hospital's plan allow):

| Role | Screens |
|---|---|
| Front desk | Patients (search, register, insurance cover), appointments, today's queue, walk-in visits |
| Nurse | Queue with triage and vitals, visit workspace |
| Doctor | Own queue (call in), visit workspace: SOAP notes, ICD-10 diagnoses, prescriptions, lab orders, complete visit |
| Lab tech | Lab work list (collect, result, complete), walk-in orders, printable report, test prices |
| Pharmacist | Pharmacy queue and dispensing, drugs and stock |
| Cashier | Invoices, payments and receipts, insurance claims, daily summary |
| Admin | All of the above plus reports, staff, departments, fees, insurers and settings |

Each screen loads on first use, which keeps the initial download around 100 KB gzipped. Charts use one series colour, `brand-600`, which clears 3:1 contrast on white; every chart also has a table view.

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
| `GET /api/v1/platform/hospitals/<id>/` | One hospital, with its usage (staff, patients, recent visits, last activity) and payments. The list takes `?search=` |
| `POST /api/v1/platform/hospitals/<id>/extend/` | Give 1-90 extra days of access (`days`, `reason`); audited |
| `GET /api/v1/platform/overview/` | Hospitals by state, monthly recurring revenue, money collected per month, and who needs attention |
| `GET/PUT /api/v1/platform/providers/...` | Choose, configure, test and switch the email and SMS providers (see [Email and SMS providers](#email-and-sms-providers)) |
| `GET /api/v1/platform/signups/` | Signups (`?status=`, `?search=`); `POST .../<id>/retry/` retries a failed or stuck one |

**Operator dashboard:** the same things as web screens, at `https://<platform domain>/operator`. Sign in with a platform superuser (create one with `python manage.py createsuperuser` on the platform). It shows:
- the overview: revenue, trials ending this week, overdue and lapsed hospitals
- every hospital, with its usage, payments and actions: extend access, record a bank transfer, change plan, suspend or reactivate
- every signup, with a retry for failed ones

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
| `revoke_patient_privileges [--dry-run]` | Remove superuser/staff/admin rights from patient accounts in every schema. **Run once after upgrading**: before the registration fix, anyone could create such accounts |
| `database_report` | JSON summary per schema (row counts, migrations, audit protection), used to verify backups |
| `launch_check [--email you@x.com] [--sms <number>]` | Is this deployment ready for real hospitals? Checks domains, email, Paystack, prices, Sentry, SMS and the legal text, optionally sends a test email and SMS, and lists what to fix. Exits with 1 while something blocks launch |
| `run_hourly` | The hourly cron job: SMS appointment reminders and subscription notices to hospital admins |
| `export_hospital --schema <hospital> [--output file.zip]` | All of a hospital's records as a ZIP of CSV files, e.g. for a hospital that has left. Contains patient data: hand it over securely |
| `process_signups [--retry-failed]` | Finish hospital setups interrupted part-way (e.g. by a deploy) and delete signups never verified. Runs on every deploy |
| `seed_notifications --schema <hospital> [--reset]` | **Demo only:** fill a demo hospital's notification centres with realistic notifications from its records (run by `seed_demo`; refuses hospitals without demo data) |
| `seed_demo --schema <hospital>` | **Local/demo only:** realistic mock data (30 days of visits, billing, claims, a live queue). Creates demo staff with a shared password, so never run it on a live server |

## Roles and access

Within a hospital, access is enforced on every endpoint with `authentication.permissions.allow_roles`. Superusers can do everything in their own hospital.

Security around sign-in and the web app:
- **Sign-in protection:** account lockout and failed-attempt logging apply to every password sign-in, the API and the Django admin alike ([authentication/backends.py](authentication/backends.py)).
- **Locked to the platform:** shared platform data (hospitals, prices, subscriptions, ICD-10 codes, provider keys, legal text) can only be edited on the platform's admin, never from a hospital's.
- **Content-Security-Policy:** the web app is served with one. Only scripts from the app's own origin run, plus its one inline config script (allowed by hash). Pages can't be framed, and error reports may only go to the Sentry host in `SENTRY_FRONTEND_DSN`.

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

### Importing patients

Clinics moving from paper or Excel can bring in their patient list under *Patients → Import* (admin, front desk).

- **Files:** `.xlsx` or `.csv`, up to 5,000 patients and 5 MB. Download the template from the page (`GET /api/v1/patients/import-template/`), or use your own sheet. Common column names are recognised: *Surname*, *DOB*, *Sex*, *Mobile*, *Card number*, *Folder number*...
- **Values:** dates as `31/12/1990` or `1990-12-31`; gender as M/F/Male/Female/Other. Phone numbers that Excel stored without their leading 0 get it back.
- **Checks:** `POST /api/v1/patients/import/` with the `file` checks every row with the same rules as registering a patient, and saves nothing (`dry_run` is true by default). Problems come back by row and column, including repeated record numbers or emails, and possible duplicates of registered patients (same name and date of birth).
- **Saving:** send `dry_run=false` to save. If any row has a problem, nothing is saved unless `skip_invalid=true`, which imports only the good rows.
- Patients without an existing record number get a new one. The import is audited.

### Exporting a hospital's records

Hospital admins can download everything their hospital has recorded under *Settings → Export all records* (`POST /api/v1/hospital/export/` with their `password`).

- **What's in it:** a ZIP with one CSV file per kind of record (users without passwords, patients, appointments, visits, vitals, consultations, diagnoses, prescriptions, lab, pharmacy, billing, insurance, SMS, audit log), plus a README and a manifest of row counts.
- **Opening it:** the files open in Excel. `<name>_id` columns link rows across files.
- **Safeguards:** the admin's password is required, and every export (and every refused attempt) is in the audit log. It's limited to 5 per hour (`THROTTLE_EXPORT`).
- **Formulas:** text a spreadsheet would run as a formula is prefixed with `'`.
- **Lapsed hospitals:** export still works when a hospital is read-only, because hospitals own their data.
- **On a hospital's behalf** (e.g. after it leaves): `export_hospital`.

### Notifications

Staff get notified in the web app (the bell in the header, and a Notifications page) when something needs them. Each notification links to the screen to open.

| When | Who |
|---|---|
| A patient joins a doctor's queue (walk-in or check-in) | That doctor |
| Emergency triage or critical vital signs (urgent) | That doctor and the nurses |
| Lab tests ordered / all results ready | Lab technicians / the ordering doctor |
| A consultation includes prescriptions | Pharmacists |
| A visit is completed with an unpaid invoice | Cashiers |
| A drug is running low | Pharmacists and admins |
| An insurer approves, rejects or pays a claim | Cashiers and admins |
| An appointment is booked or cancelled | The doctor |
| The trial ends in 7, 3 or 1 days, payment is overdue, or records are read-only | Hospital admins |

- **Rules:** nobody is notified about their own action. A repeat alert (e.g. low stock on every dispense) isn't added while an identical one is unread. Inactive staff get nothing.
- **Under the hood:** notifications come from the domain events ([notifications/alerts.py](notifications/alerts.py)), so adding one is a single handler.
- **Subscription notices** come from `notify_subscription_status`. It runs in the hourly job (`run_hourly`, the `hms-reminders` cron job) together with the SMS reminders.
- **API:** `GET /api/v1/notifications/` (`?unread=true`), `GET .../unread-count/` (the app checks every 30 seconds), `POST .../<id>/read/`, `POST .../read-all/`.

### Email and SMS providers

Who delivers the platform's email and SMS is chosen at runtime by a platform operator, in the operator dashboard (*Providers*) or through the API. It can be switched at any time without a deploy.

| Channel | Providers |
|---|---|
| Email (signup, password resets, welcome) | **ZeptoMail** (Zoho), or any **SMTP** server |
| SMS (appointment confirmations and reminders) | **Termii** |
| Both, in development | **Console**: prints messages instead of sending them. Never allowed as the active provider in production |

How it works:
1. **Save** a provider's settings: `PUT /api/v1/platform/providers/<channel>/<provider>/` with its fields, e.g. ZeptoMail's `api_token`, `api_host`, `from_email`. Secret fields left blank keep their saved value.
2. **Test** it: `POST .../<channel>/<provider>/test/` with `{"to": "you@x.com"}` or a mobile number. The result is stored, with the provider's own error message if it fails.
3. **Switch** to it: `PUT /api/v1/platform/providers/<channel>/` with `{"provider": "zeptomail"}`. This only works after a successful test of the current settings, and any later change to the settings needs a new test. `{"provider": null}` goes back to the server settings.

Safeguards:
- **Encrypted keys:** API keys are stored encrypted with `PROVIDER_ENCRYPTION_KEY` and never returned (only `••••a1b2`).
- **Restricted and audited:** only platform superusers can change providers, and every save, test and switch is audited.
- **Fallback:** without a chosen provider, the server settings apply: `EMAIL_BACKEND`/`EMAIL_HOST...` for email, and `SMS_BACKEND`/`SMS_API_KEY...` for SMS.
- **Adding a provider** is one class in [providers/registry.py](providers/registry.py). The dashboard form is built from its declared fields.

Setting up ZeptoMail: verify your sending domain in ZeptoMail (DNS records). Then copy the Send Mail token from *Mail Agents → your agent → SMTP/API*. The API host depends on your account's region (`api.zeptomail.com`, `.eu`, `.in`…).

Setting up Termii: copy the API key and your account's base URL. Get a sender ID approved, and ask Termii to activate the **DND** route so messages reach numbers on Do-Not-Disturb.

### Patient SMS

Appointment confirmations (when booked or moved) and reminders (the morning before), so fewer patients miss appointments.

- **Hospitals switch them on** under *Settings → Patient SMS*, and may set a sender name (registered with the provider first).
- **Skipped, with the reason recorded:** patients ticked "Don't send appointment SMS", patients without a valid mobile number, and anything over the hospital's monthly cap (`SMS_MONTHLY_LIMIT_PER_HOSPITAL`, default 500).
- **Numbers:** written as `0803...` they are treated as Nigerian (`SMS_DEFAULT_COUNTRY_CODE`).
- **Sending:** confirmations are sent in the background right after booking. Reminders come from `python manage.py send_appointment_reminders` (part of `run_hourly`), run hourly (the `hms-reminders` cron job in render.yaml). Each hospital's reminders go out once its local time reaches `SMS_REMINDER_HOUR` (default 9), never twice, and not for lapsed hospitals.
- **Delivery:** through the SMS provider chosen in the operator dashboard (Termii; see [Email and SMS providers](#email-and-sms-providers)). In development, messages print in the `runserver` console.
- **History:** `GET /api/v1/sms-messages/?patient=<id>` (admin, front desk) lists what was sent, failed or skipped, and why.

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

### Reports

Every report takes `?date_from=&date_to=` (`YYYY-MM-DD`, in hospital time). The default is the last 30 days, and the maximum range is a year.

| Endpoint | Shows | Who |
|---|---|---|
| `/api/v1/reports/clinical/` | Visits by day, status, triage and doctor; average waiting and consultation time; new patients; top ICD-10 diagnoses | admin |
| `/api/v1/reports/financial/` | Money collected (patients vs insurers, by method, by day); charges by category; receivables with 0-30 / 31-60 / 61-90 / 91+ day aging; amounts owed by each insurer | admin, cashier |
| `/api/v1/reports/pharmacy/` | Most dispensed drugs, low stock, stock value, drugs without a price | admin, pharmacist |
| `/api/v1/reports/lab/` | Tests by type and status, average turnaround time, pending work | admin, lab tech |

### Passwords and monitoring

- **Password resets:**
  - Admins reset a staff member's password from **Staff → Reset password**. This issues a temporary password shown once, signs the person out everywhere and unlocks the account. They must choose their own password at next sign-in.
  - Staff can also use **Forgot password?** on the sign-in page. The emailed link works once and expires after an hour, and the page never reveals whether an email has an account.
  - Emails go through the email provider chosen in the operator dashboard (see [Email and SMS providers](#email-and-sms-providers)). Locally they print in the `runserver` console.
- **Error monitoring:** set `SENTRY_DSN` (API) and `SENTRY_FRONTEND_DSN` (web app) to report errors to Sentry, which has a free tier.
  - Reports include the stack trace, hospital, request id and the user's internal id and role.
  - **Never** sent: request bodies, query strings (searches can contain patient names), cookies, auth headers, local variables, or names and emails. See [helpers/monitoring.py](helpers/monitoring.py).
  - In the web app, a crash shows a "Something went wrong" screen instead of a blank page.

### Terms of service and privacy policy

Shown at `/terms` and `/privacy` on the platform site, and linked from the footer and the signup form. Signing up requires accepting them, and each signup records the versions it accepted.

- **Edit in the platform admin** (*Terms and privacy*), using simple formatting: `# ` heading, `## ` subheading, `- ` list item, a blank line between paragraphs.
- **Versions:** published versions are locked, because people accepted them. To change a document, add a new version and use the *Publish* action; it becomes the current one.
- **Drafts:** the seeded documents (`draft-1`, from [legal/drafts.py](legal/drafts.py)) are starting drafts with `[placeholders]`, not legal advice. They show a "draft, under legal review" notice until a version is published with *draft* unticked.

### Self-serve signup

Hospitals can sign themselves up at the platform address (e.g. `yourdomain.com/signup`). The platform site also has a landing page with prices, and a "Sign in" page that sends people to their hospital's own address.

1. **Sign up:** the owner gives the hospital's name, its web address (e.g. `st-lukes` for `st-lukes.yourdomain.com`), a plan for the trial, and their own details and password. The API checks the address is free and not reserved (`www`, `api`, `admin`...) and that the password is strong, then **emails a verification link. Nothing is created yet.**
2. **Verify:** opening the link creates the hospital: its schema, the owner's admin account (with the password they chose) and a free trial of the chosen plan. This takes 10-60 seconds, longer than a web request should, so it runs in a background thread while the page shows progress. A welcome email follows.
3. **Sign in** at the hospital's own address.

Abuse protection:
- Nothing heavy happens before the email is verified.
- 5 signups per hour per IP (`THROTTLE_SIGNUP`), and 3 per email address per day.
- A hidden form field catches bots.
- The page never reveals whether an email is already in use.

Signups are kept in the platform admin (*Signups*). A deploy can interrupt a setup in progress; `process_signups` runs on every deploy to finish it, and also deletes signups never verified after 7 days, since they hold personal details. Locally, the verification email prints in the `runserver` console.

API (platform domain, no sign-in): `POST /api/v1/signup/`, `GET /api/v1/signup/availability/?address=`, `GET /api/v1/signup/plans/`, `POST /api/v1/signup/verify/` and `POST /api/v1/signup/status/` (both take `{"token"}`).

### Subscriptions (what hospitals pay)

Every new hospital starts with a **14-day free trial**. Its administrators pay under **Subscription** in the web app, monthly or yearly, through Paystack (card, bank or USSD). Prices live in the platform admin (*Plan prices*). They are seeded with placeholders, so set your own before launch.

| State | Access |
|---|---|
| Trial or paid period | Everything the plan includes |
| Up to 7 days overdue (grace) | Everything, with a warning banner |
| After the grace period, or cancelled and expired | **Read-only**: records stay viewable (patient care never stops), but changes get `402` until someone pays. Signing in and paying still work. |

How payments are trusted:
- The browser's word is never taken. When a payer returns from Paystack, the API asks Paystack to verify the payment and checks the hospital, plan, amount and currency.
- Renewals arrive by webhook and are accepted only with a valid Paystack signature.
- Each payment reference counts once, however often it arrives.
- Paying early adds to the time remaining. Paying late starts from today.

Setup:
1. Set `PAYSTACK_SECRET_KEY`. Use `sk_test_...` first; Paystack test cards work end to end.
2. In the Paystack dashboard (*Settings → API Keys & Webhooks*), set the webhook URL to `https://<platform domain>/api/v1/platform/billing/paystack/webhook/`.
3. Run `python manage.py sync_paystack_plans` to create matching Paystack plans, which enables automatic renewal. After changing a price, run it again with `--reprice`.

Bank transfers: the platform records them with `POST /api/v1/platform/hospitals/<id>/record-payment/` (`plan`, `interval`, `amount`, `reference`, `note`). Payments and subscriptions are visible in the platform admin. Without a Paystack key, the Subscription page tells admins to pay by transfer.

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

The product's name on the website, emails, admin and API docs comes from `PRODUCT_NAME` (default `HMS`), so renaming needs no code change.

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

Step by step, with every setting and day-to-day operations: [docs/RUNNING_AND_HOSTING.md](docs/RUNNING_AND_HOSTING.md#3-host-it-on-render). In short:

Production runs as **one Docker service** ([Dockerfile](Dockerfile)): it builds the web app, and Django serves it at each hospital's address next to the API. That means the same origin, no CORS setup, and a first-party session cookie. The service is described in [render.yaml](render.yaml).

1. **Database:** use your existing Render Postgres (back it up first), or create one for a new install. The blueprint deliberately doesn't create one.
2. **Create the service:** in the Render dashboard, choose *New → Blueprint* and pick this repository. Fill in:
   - `DATABASE_URL`: your Postgres internal URL
   - `TENANT_BASE_DOMAIN`: e.g. `yourdomain.com`
   - `PLATFORM_DOMAINS`: e.g. `yourdomain.com`

   `SECRET_KEY` is generated automatically. For subscriptions, also set `PAYSTACK_SECRET_KEY` (see [Subscriptions](#subscriptions-what-hospitals-pay)).
3. **Domains:** add `yourdomain.com` and the wildcard `*.yourdomain.com` to the service, and create the DNS records Render shows you. Each hospital then lives at `<name>.yourdomain.com`.
4. **Each deploy** runs `migrate` (every hospital's schema) and `setup_platform` before switching traffic. The health check is `/api/health/`.
5. **Check readiness:** in the Shell, run `python manage.py launch_check --email you@example.com`, and fix what it reports.
6. **Create hospitals** from the service's Shell tab (`python manage.py create_hospital ...`) or through the platform API.

The Docker image needs no other configuration: the hospital domain is injected into the web app at runtime (`window.__HMS_CONFIG__`), so one build works on any domain. To deploy without Docker, build the frontend (`cd frontend && npm ci && npm run build`) before `collectstatic`; Django serves `frontend/dist` when it exists.

### Backups

See **[docs/BACKUP_AND_RESTORE.md](docs/BACKUP_AND_RESTORE.md)**: Render's managed backups, `scripts/backup.sh` before risky changes, a monthly restore drill (`scripts/restore_drill.sh`, tested) and the real-restore procedure. Backups contain patient data: never commit them (`backups/` is git-ignored).

### Upgrading the existing single-hospital deployment

Before multi-tenancy, all data lived in the `public` schema. To move it into a hospital:

1. **Back up the database.**
2. Deploy as above. Migrations prepare the shared schema and register the platform.
3. In the service Shell, run:

   ```bash
   python manage.py create_hospital --name "Main Hospital" --schema main --admin-email you@example.com
   python manage.py adopt_legacy_data --schema main --force
   python manage.py revoke_patient_privileges
   ```

   - `create_hospital` creates the hospital.
   - `adopt_legacy_data` copies your data into it. `--force` is needed because the new hospital already contains its setup admin; the copy replaces that admin with your existing users, who keep their passwords.
   - `revoke_patient_privileges` removes admin rights from patient accounts created through the old open registration.
4. Open `https://main.yourdomain.com`, sign in and check the data. The original tables in `public` are left untouched until you choose to drop them.
