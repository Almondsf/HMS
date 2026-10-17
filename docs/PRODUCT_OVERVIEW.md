# HMS: Product and System Overview

This document explains what HMS is, who uses it, what it does, and how it is built. Read it before diving into the code. For setup commands and the full endpoint reference, see the [README](../README.md). For what each kind of user needs, see [USER_STORIES.md](USER_STORIES.md).

---

## 1. What HMS is

HMS is **hospital management software sold as a subscription** (SaaS). Clinics and hospitals sign up, pay monthly or yearly, and run their day-to-day work in it:
- registering patients and booking appointments
- managing the waiting queue, triage and vital signs
- doctors' consultation notes, diagnoses and prescriptions
- laboratory tests and results
- pharmacy stock and dispensing
- billing, payments and receipts
- HMO / insurance claims
- management reports

One installation serves **many hospitals**. Each hospital gets its own web address (e.g. `stlukes.yourdomain.com`), and its data is kept completely separate from every other hospital's.

It is built first for **Nigerian and West African** clinics: naira pricing, Paystack payments, NHIA and HMOs, genotype on patient records, and a starter list of common local diagnoses. Currency and timezone are configurable per hospital, so it isn't limited to Nigeria.

### The two sides of the product

| | Who | Where | What they do |
|---|---|---|---|
| **Hospital app** | Hospital staff | `<hospital>.yourdomain.com` | Run the hospital |
| **Platform** | You, the software's owner/operator | `yourdomain.com` | Create hospitals, set prices, record payments, suspend hospitals |

---

## 2. Who uses it

| Role | Typical person | Main work in HMS |
|---|---|---|
| **Admin** | Medical director, hospital manager | Staff accounts, departments, prices (fees), insurers, settings, reports, the hospital's subscription. Can see everything. |
| **Receptionist** (front desk) | Front desk / records officer | Registers patients, books appointments, checks patients in, opens walk-in visits, records insurance cover, takes payments |
| **Nurse** | Triage nurse | Triages waiting patients, records vital signs |
| **Doctor** | Any doctor | Calls patients in from their queue, writes consultation notes, diagnoses, prescribes, orders lab tests, completes visits |
| **Lab technician** | Lab scientist | Works the lab list: collects samples, enters results, prints reports |
| **Pharmacist** | Pharmacist | Dispenses prescriptions, manages drug stock and prices |
| **Cashier** | Accounts / cashier | Issues invoices, takes payments, prints receipts, handles insurance claims, end-of-day summary |
| **Patient** | Patient | Has a record. Can be given a login to view their own visits and invoices through the API (there is no patient web app yet). |
| **Platform operator** | You | Works on the platform site, not inside hospitals |

A user has exactly one role. The web app's sidebar shows each role only the screens it may use. The API enforces the same rules independently, so hiding a screen is never the only protection.

---

## 3. Plans and pricing

Hospitals pay for a **plan**. The plan decides which modules they get:

| Plan | Modules | Placeholder price |
|---|---|---|
| **Basic** | Front desk & clinical, Pharmacy, Billing | ₦25,000 / month |
| **Pro** | Basic + Laboratory + Insurance claims | ₦60,000 / month |
| **Enterprise** | Everything | ₦150,000 / month |

Prices are placeholders, edited in the platform admin. Yearly costs 10× monthly (two months free). If a hospital calls an endpoint its plan doesn't include, the API returns 403 and says why.

**Subscription lifecycle:**

```
new hospital ──▶ 14-day free trial ──pay──▶ active ──period ends unpaid──▶ 7-day grace (warning banner)
                                              ▲                                   │
                                              └────────────── pay ◀── read-only ◀─┘
```

- **Read-only** means staff can still sign in and *view* every record (patient care must never be blocked by a billing problem), but nothing new can be saved until someone pays. Blocked changes get HTTP `402`.
- **Payment methods:** Paystack (card, bank, USSD) with automatic renewal, or bank transfer recorded by the platform operator.
- **Suspension** is separate. The platform operator can switch a hospital off completely (`is_active = false`), e.g. for abuse.

---

## 4. A day at a hospital (the main workflow)

This is the path most features hang off. Knowing it makes the code much easier to follow.

```
 FRONT DESK                 NURSE               DOCTOR                       LAB / PHARMACY          CASHIER
 ──────────                 ─────               ──────                       ──────────────          ───────
 register patient
 book appointment
 check in ─────▶ visit opens (waiting) ──▶ triage + vitals ──▶ call in (in consultation)
   (or walk-in)    │ invoice opens,                             SOAP notes, diagnoses
                   │ card fee charged                           prescribe ──────────────▶ dispense ─┐
                   │                                            order lab ──────────────▶ results ──┤ each adds
                   │                                            complete visit                       │ a charge
                   ▼                                                                                 ▼
                                                                                               issue invoice
                                                                                               take payment / claim HMO
                                                                                               print receipt
```

Key ideas:
1. **The visit is the centre.** Consultations, vitals, lab orders, prescriptions and charges all hang off a visit.
2. **Billing is automatic.** Every billable action adds a line to the visit's draft invoice *in the same database transaction* as the action. A service can never be delivered without its charge being recorded, and a charge can never exist for a service that failed.
3. **Care is never blocked by billing.** An unpriced item is charged at ₦0 and flagged. The cashier must price it before issuing the invoice, but the doctor, lab and pharmacy keep working.

---

## 5. Features in detail

### 5.1 Accounts and security
- Sign in with **email and password**. Sessions use short-lived access tokens (15 min) and refresh tokens (7 days) that rotate and can be revoked.
- In the browser, the refresh token lives in an **httpOnly cookie**, so scripts can't steal it. Nothing is kept in localStorage.
- **Account lockout** after repeated failed sign-ins. Sign-in and password-reset requests are **rate limited**.
- **Two-factor sign-in** with an authenticator app, required for platform operators and hospital admins, optional for other staff. Recovery codes cover a lost phone, and admins can reset a colleague's.
- **Password resets:** an admin can issue a temporary password, which the person must change at next sign-in. Staff can also reset by email link, which works once and expires in an hour.
- Deactivating a staff member signs them out everywhere. Accounts are deactivated, never deleted, so history stays intact.
- Tokens only work at the hospital that issued them.

### 5.2 Patients and staff
- **Patient registry** with an automatic **medical record number** (MRN), e.g. `SLH-000123`. The prefix is set per hospital. Numbers never collide or change, and existing paper numbers can be kept.
- Patient details include demographics, blood group, genotype, allergies, medical history and an assigned doctor. Email and password are optional, since most patients never sign in.
- Search matches every word against name, MRN, phone and email.
- **Staff directory** by role and department. The admin creates staff accounts.

### 5.3 Appointments and queue
- Book, reschedule, cancel and mark no-shows. **No double-booking** of a doctor or a patient, even under simultaneous requests.
- **Check-in** on the day turns an appointment into a visit in the doctor's queue. Walk-ins skip the appointment.
- **Today's queue** shows who is with the doctor, then who is waiting, ordered by **triage priority** and then arrival time, with waiting minutes.
- **SMS:** a confirmation when an appointment is booked or moved, and a reminder the morning before. Each hospital switches them on. Patients can opt out, and every message (or the reason one wasn't sent) is recorded. Sent through Termii. Each hospital has a monthly cap.

### 5.4 Triage and vital signs (nurses)
- Triage levels: emergency, urgent, standard, non-urgent. An **emergency** raises an event.
- Vital signs: temperature, pulse, blood pressure, breathing rate, oxygen saturation, weight, height, blood glucose and pain score (0-10). All are optional. The system calculates **BMI**, flags abnormal values (e.g. "fever", "low oxygen saturation") and marks **critical** readings, which also raise an event.
- Impossible values are rejected as typos. Readings are never edited, only superseded by new ones.

### 5.5 Consultations (doctors)
- **SOAP notes** (Subjective, Objective, Assessment, Plan) per visit.
- **Diagnoses** coded in **ICD-10**, with searchable codes. Each diagnosis is primary or secondary, and provisional, confirmed or ruled out. There is one active primary diagnosis per consultation, and diagnoses are ruled out rather than deleted.
- **Prescriptions** go straight to the pharmacy queue.
- **Lab orders** go straight to the lab work list.
- Status changes only through explicit actions: start, complete, cancel.

### 5.6 Laboratory (Pro plan)
- Test catalogue with prices. Admins and lab techs maintain it.
- Orders come from consultations, or as **walk-in** lab requests.
- Workflow per test: pending → sample collected → in progress → completed. Completing a result notifies via an event. A printable lab report is available.

### 5.7 Pharmacy
- Drug catalogue with stock levels, unit prices and low-stock thresholds.
- **Dispensing** against prescriptions. Partial dispensing is supported.
- **Concurrency-safe:** stock and prescribed quantities are locked during dispensing, so two pharmacists can never oversell the same stock.

### 5.8 Billing
- **Tariff (fees):** service items such as card fee, consultation and procedures. Some are charged automatically (every visit, every consultation); others are added by the cashier.
- **Invoices:** draft (collecting charges) → issued (lines fixed) → paid, or void. Discounts and voids need a reason and the right role.
- **Payments:** cash, card/POS, transfer, mobile money, or insurance (insurance is only through claims). Overpayment and double submission are impossible.
- Printable **receipts** and an **end-of-day cash summary** by method and cashier.

### 5.9 HMO / insurance (Pro plan)
- Providers: HMOs, NHIA, private insurers and corporate retainers, each with a default coverage % and an optional pre-authorisation requirement.
- **Patient cover:** member number, validity dates and coverage %.
- **Claims:** draft → submitted → approved/rejected → paid. While a claim is open, the patient pays only their share. Any rejected or unpaid part falls back to the patient.
- Printable **claim document** (member details, ICD-10 diagnoses, itemised charges) and an **outstanding by insurer** view for chasing payment.

### 5.10 Reports
- **Clinical:** visits by day, status, triage and doctor; waiting and consultation times; new patients; top diagnoses.
- **Financial:** collections (patients vs insurers), charges by category, receivables aging (0-30 / 31-60 / 61-90 / 91+ days), amounts owed by each insurer.
- **Pharmacy:** top drugs, low stock, stock value, unpriced drugs.
- **Lab:** volumes, turnaround time, pending work.
- Any date range up to a year, in hospital time. Every chart has a table view.

### 5.11 Data import and export
- **Import:** the front desk can bring in an existing patient list from Excel or CSV. Every row is checked first, with problems listed by row, and possible duplicates of registered patients are flagged.
- **Export:** a hospital admin can download all of the hospital's records at any time, even when the subscription has lapsed: a ZIP of CSV files that open in Excel.
- Requires the admin's password and is recorded in the audit log. Passwords are never exported.

### 5.12 Notifications
- A bell in the header and a Notifications page. Each person sees what needs them, linked to the right screen:
  - doctors: patients waiting, emergencies, critical vitals, lab results, appointments
  - nurses: emergencies and critical vitals
  - lab technicians: new requests
  - pharmacists: new prescriptions and low stock
  - cashiers: patients ready to pay and insurance claim outcomes
  - admins: low stock, claims, trial ending and overdue payment
- Nobody is told about their own action, and repeated alerts don't pile up.
- **By email:** urgent alerts and subscription notices are emailed right away, and everything else goes into a morning summary. Each person chooses what they get. Emails never name patients; they link back to the app.

### 5.13 Audit trail
- **Every change** to clinical, billing and other records, **every read of patient data**, and **every security event** (sign-ins, lockouts, resets) is recorded with who, what, when, IP and request id.
- **Append-only:** the database itself refuses to edit or delete audit rows.
- An admin can answer "**who has looked at this patient's record?**", which is a core requirement of health-data laws such as the NDPA.

### 5.14 Self-serve signup
- Anyone can sign up a hospital at the platform address. They choose its web address (e.g. `st-lukes.yourdomain.com`), a plan for the trial, and their admin password.
- Nothing is created until they confirm their email. Then the hospital is created in the background (10-60 seconds) while the page shows progress, and a welcome email follows.
- Abuse limits: email verification, rate limits per IP and per email, a hidden bot trap, and reserved addresses.
- The platform site also has a landing page with live prices, and a "Sign in" page that sends people to their hospital's address.
- Signing up requires accepting the terms of service and privacy policy (shown at `/terms` and `/privacy`). The accepted versions are recorded. The documents are edited and versioned in the platform admin.

### 5.15 Platform (for the operator)
- **Operator dashboard** at `/operator` on the platform site:
  - monthly recurring revenue, money collected per month, and hospitals by state (trial, paying, overdue, lapsed, suspended)
  - who needs attention: trials ending this week, overdue hospitals, lapsed hospitals, stuck signups
  - each hospital's usage (staff, patients, visits, last activity) and payments
  - signups and their outcome
- Actions: give extra days, record a bank-transfer payment, change plan, suspend or reactivate, retry a failed signup.
- **Providers:** choose and switch who delivers email (ZeptoMail, SMTP) and SMS (Termii) without a deploy. Every provider must pass a test message before it's used.
- Provision a hospital directly (API or command), and edit prices (platform admin).
- Paystack webhook for renewals, failed payments and cancellations.

---

## 6. How it is built

### 6.1 Technology

| Layer | Technology |
|---|---|
| API | Python 3.12, Django 5.2 LTS, Django REST Framework, JWT (simplejwt) |
| Database | PostgreSQL, one **schema per hospital** (django-tenants) |
| Web app | React 19, TypeScript, Vite, Tailwind CSS (white and sky blue), TanStack Query, React Router |
| Payments | Paystack |
| Email and SMS | ZeptoMail and Termii, switchable at runtime by the platform operator (SMTP also supported) |
| Monitoring | Sentry (scrubbed of patient data), structured JSON logs with request ids |
| Hosting | One Docker service on Render; Django serves both the API and the built web app |
| Quality | GitHub Actions: lint (ruff), tests on Postgres with ≥85% coverage, dependency audit, frontend build, Docker boot check |

### 6.2 Multi-tenancy (how hospitals are kept apart)

```
stlukes.yourdomain.com ──▶ middleware finds hospital "stlukes" ──▶ Postgres search_path = stlukes
mercy.yourdomain.com   ──▶ middleware finds hospital "mercy"   ──▶ Postgres search_path = mercy
yourdomain.com         ──▶ platform site                       ──▶ public schema
```

- **Public schema** (shared): hospitals, their domains, subscriptions, prices, ICD-10 codes.
- **Each hospital's schema:** its users, patients, visits, invoices, audit log, everything else.
- A query in one hospital physically cannot read another hospital's tables. Login tokens carry the hospital they were issued for and are rejected anywhere else.

### 6.3 Code layout

Each Django app is one area of the business:

| App | Owns |
|---|---|
| `authentication` | Users, roles, login, tokens, lockout, password reset, permission helpers |
| `profiles` | Patient and staff profiles, departments, MRN sequence |
| `scheduling` | Appointments |
| `clinical` | Visits, queue, triage, vitals, consultations, diagnoses, prescriptions |
| `lab` | Test catalogue, orders, results |
| `pharmacy` | Drugs, dispensing |
| `billing` | Tariff, invoices, lines, payments, receipts |
| `insurance` | Providers, cover, claims |
| `reports` | Read-only management reports |
| `audit` | Audit trail and domain events |
| `terminology` | ICD-10 codes |
| `tenants` | Hospitals, domains, provisioning, plans/features, platform API |
| `subscriptions` | Prices, subscriptions, Paystack, read-only enforcement |
| `helpers` | Shared plumbing: error format, logging, monitoring, test helpers |
| `hms` | Settings, URL routing, serving the web app |
| `frontend` | The React web app |

### 6.4 How a request flows

```
request → middleware (hospital, timezone, subscription, request id)
        → view (who may do this? which rows may they see?)
        → serializer (is the input well-formed?)
        → service (business rules, in a transaction) → models → Postgres
                    └─▶ audit record + domain event (sent after commit)
```

Rules every backend developer should know:
1. **Business rules live in `services.py`**, not in views or serializers. Services raise Django `ValidationError`/`PermissionDenied`, which become clean 400/403 JSON responses.
2. **Permissions are declared per endpoint** with `allow_roles(read=[...], write=[...])`, and plan modules with `requires_feature(...)`.
3. **Nothing medical is hard-deleted.** Foreign keys use `PROTECT`; records are deactivated, voided or ruled out instead.
4. **Changes to records are audited automatically** for registered models. `queryset.update()` bypasses that, so record audit events by hand when you use it.
5. **Code outside a web request** (commands, jobs) must choose a hospital first with `tenant_context(hospital)`.

### 6.5 Domain events

Services publish named events after their transaction commits. Other code subscribes to them without the publisher knowing (this is how SMS reminders and notifications will be added). Each event is also stored in the audit trail.

| Area | Events |
|---|---|
| Scheduling | `appointment_booked`, `appointment_rescheduled`, `appointment_cancelled`, `appointment_no_show`, `patient_checked_in` |
| Clinical | `visit_opened`, `patient_triaged`, `emergency_arrival`, `critical_vitals`, `consultation_recorded`, `diagnosis_recorded`, `diagnosis_updated` |
| Lab | `order_placed`, `result_completed`, `order_completed` |
| Pharmacy | `dispensed`, `stock_low` |
| Billing | `invoice_issued`, `invoice_paid`, `invoice_voided`, `payment_received`, `payment_voided` |
| Insurance | `claim_created`, `claim_submitted`, `claim_paid` |
| Platform | `hospital_provisioned` |

Billing subscribes to clinical events *inside* the transaction (`in_transaction=True`), which is what makes charging atomic with care.

### 6.6 Main data model (simplified)

```
Hospital ─1:1─ Subscription ─1:n─ SubscriptionPayment            (public schema)

inside each hospital schema:
User ─1:1─ PatientProfile / DoctorProfile / NurseProfile / ...
PatientProfile ─1:n─ Appointment
PatientProfile ─1:n─ Visit ─┬─ VitalSigns (n)
                            ├─ Consultation ─┬─ Diagnosis (n) ── Icd10Code
                            │                ├─ Prescription (n) ── Drug ── DispensedItem
                            │                └─ TestOrder ── TestResult (n) ── LabTest
                            └─ Invoice ─┬─ InvoiceLine (n) ── ServiceItem / LabTest / Drug
                                        ├─ Payment (n)
                                        └─ Claim ── Coverage ── InsuranceProvider
AuditEvent (append-only, references any of the above)
```

### 6.7 API conventions
- Everything is under `/api/v1/`. Interactive docs are at `/api/docs/` on any hospital's address.
- Lists are paginated (`?page=`, `?page_size=` up to 100) and filterable by query parameters.
- Errors are always JSON: `{"field": ["message"]}` for validation, otherwise `{"detail": "..."}` plus a `request_id` for server errors.
- Every response carries `X-Request-ID`. Quote it to find matching logs and audit events.

### 6.8 Security and privacy summary

| Concern | How it's handled |
|---|---|
| Hospital data isolation | Separate Postgres schema per hospital; tokens bound to their hospital |
| Stolen sessions | httpOnly refresh cookie, 15-min access tokens, rotation and revocation |
| Password guessing | Lockout on every sign-in (API and Django admin), rate limits, Argon2 hashing, strength validation |
| Stolen passwords | Two-factor sign-in (authenticator app) required for operators and hospital admins; codes work once |
| Injected scripts (XSS) | No raw HTML is ever rendered, and a Content-Security-Policy lets the browser run only our own scripts |
| Insider snooping | Every patient-record read is audited; the audit log is append-only |
| Data leaks via error reports | Sentry never receives request bodies, query strings, names or emails |
| Leaked provider keys | Email and SMS API keys are encrypted in the database and never shown again; changes are audited |
| Fake payments | Payments verified with Paystack server-side; webhooks signature-checked; each reference counted once |
| Transport | HTTPS forced in production, HSTS, secure cookies |
| Data loss | Managed Postgres backups plus a tested restore drill ([BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md)) |

---

## 7. What is not built yet

| Item | Status |
|---|---|
| Phone push notifications (in-app and email are built) | Would reuse the same rules |
| Patient-facing web or mobile app | Not started; the API already supports patient logins |
| Inpatient care (wards, beds, admissions), theatre, maternity | Not started |
| Enterprise features (SSO, multi-branch, custom domains) | Phase 5 |

---

## 8. Glossary

| Term | Meaning |
|---|---|
| **Tenant** | A hospital, in the code's vocabulary |
| **Schema** | A separate namespace of tables inside Postgres; each hospital has one |
| **Platform / public schema** | The shared part that knows about all hospitals |
| **MRN** | Medical record number, the patient's permanent hospital number |
| **SOAP** | Subjective, Objective, Assessment, Plan: the standard structure of consultation notes |
| **ICD-10** | The WHO's international list of diagnosis codes |
| **Triage** | Sorting patients by urgency |
| **HMO** | Health Maintenance Organisation, a Nigerian health insurer |
| **NHIA** | National Health Insurance Authority, Nigeria's national scheme |
| **Tariff** | The hospital's price list |
| **Draft / issued invoice** | Draft is still collecting charges; issued is final and payable |
| **Domain event** | A named business occurrence (e.g. `lab.result_completed`) that other code can react to |
| **Grace period** | The 7 days after a missed renewal when everything still works |
| **402** | The HTTP status the API returns when a lapsed hospital tries to change data |
