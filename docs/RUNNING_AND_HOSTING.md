# Running and Hosting HMS

How to run HMS on your computer, put it on the internet, and keep it running. For what the product does, see [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md). For the API and every feature's details, see the [README](../README.md).

> Keep this guide current: any change to setup, settings, commands or hosting updates this file in the same commit.

---

## 1. What runs where

```
                       ┌──────────────── Render ────────────────┐
 yourdomain.com  ─────▶│  Web service "hms" (one Docker image)  │
 *.yourdomain.com      │   Django API + the React web app       │──▶ PostgreSQL (one schema per hospital)
                       │  Cron job "hms-reminders" (hourly)     │
                       │   SMS reminders, subscription notices  │
                       └────────────────────────────────────────┘
                              │          │          │         │
                           Email     Paystack    SMS      Sentry
                          (Brevo…)  (payments) (Termii…)  (errors)
```

| Address | What it is |
|---|---|
| `yourdomain.com` | The platform site: landing page, prices, signup, terms, and `/operator` (your dashboard) |
| `<hospital>.yourdomain.com` | A hospital's web app and API, e.g. `stlukes.yourdomain.com` |
| `<hospital>.yourdomain.com/api/docs/` | Interactive API documentation |
| `yourdomain.com/admin/` | Django admin for the platform: prices, legal text, signups (change the path with `ADMIN_URL`) |

---

## 2. Run it on your computer

### 2.1 What you need

| Tool | Version | Check with |
|---|---|---|
| Python | 3.12 | `python --version` |
| PostgreSQL | 16 or newer | `psql --version` |
| Node.js | 22 or newer (the server build uses 24) | `node --version` |
| Git | any | `git --version` |

### 2.2 First-time setup

Windows (Git Bash or PowerShell); on macOS/Linux use `source venv/bin/activate` instead.

```bash
git clone https://github.com/Almondsf/HMS.git && cd HMS

# Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env            # set DB_NAME, DB_USER, DB_PASSWORD for your Postgres
createdb hms                    # or create the "hms" database in pgAdmin
python manage.py migrate        # creates the shared tables and every hospital's
python manage.py setup_platform # registers localhost as the platform site

# A hospital with realistic demo data
python manage.py create_hospital --name "Main Hospital" --schema main --admin-email you@example.com
python manage.py seed_demo --schema main     # 30 days of patients, visits, bills, claims, notifications

# Web app
cd frontend
npm install
cd ..
```

`create_hospital` prints the admin's one-time password. `seed_demo` creates demo staff, one per role, all sharing one password. Write the logins into `DEMO_CREDENTIALS.md`, which git ignores. **Never run `seed_demo` on a live server.**

To use the operator dashboard locally, make a platform operator: `python manage.py createsuperuser`.

### 2.3 Start it (every time)

Two terminals:

```bash
# Terminal 1: API (http://localhost:8000)
venv\Scripts\activate
python manage.py runserver

# Terminal 2: web app with live reload (http://localhost:5173)
cd frontend
npm run dev
```

Then open:

| Address | What |
|---|---|
| http://main.localhost:5173 | The demo hospital (sign in with a demo login) |
| http://localhost:5173 | The platform site: landing page, signup, terms |
| http://localhost:5173/operator | The operator dashboard (platform superuser) |
| http://main.localhost:8000/api/docs/ | API documentation |
| http://localhost:8000/admin/ | Django admin (platform) |

`*.localhost` addresses work in browsers on every system, with no setup. For `curl`, send the hospital's name as the host: `curl -H "Host: main.localhost:8000" http://127.0.0.1:8000/api/health/`.

**Emails and SMS don't leave your computer:** they print in the `runserver` terminal. Signup verification links, password resets and appointment SMS appear there.

### 2.4 With Docker instead

```bash
docker compose up                # Postgres + the API on http://localhost:8000
docker compose exec web python manage.py create_hospital --name "Main Hospital" --schema main --admin-email you@example.com
docker compose exec web python manage.py seed_demo --schema main
```

Compose runs the API and database. Run the web app with `npm run dev` as above.

### 2.5 Tests and checks

GitHub Actions runs everything on each push (lint, tests with an 85% coverage floor, dependency audit, web build, Docker boot). To run them yourself:

```bash
ruff check . && ruff format --check .
pytest                           # about 10 minutes; one module: pytest notifications
cd frontend && npm run build     # type-checks the web app
```

---

## 3. Host it on Render

### 3.1 Before you start

- [ ] A **domain** (e.g. from Namecheap, or Whogohost for `.ng`).
- [ ] A **Render** account, with a payment method (the database and cron job are paid).
- [ ] An **email provider** for signup and password emails, e.g. Brevo (free tier).
- [ ] Optional now, needed before charging hospitals: **Paystack** (allow days for business verification), **Sentry**, **Termii** or **Africa's Talking**.

### 3.2 Deploy

1. **Database.** Use your existing Render Postgres (**back it up first**, see §4.5) or create one. Copy its *Internal Database URL*.
2. **Create the services.** Render → *New → Blueprint* → choose this repository. It reads [render.yaml](../render.yaml) and creates:
   - `hms`: the web service (API and web app)
   - `hms-reminders`: an hourly cron job, which takes its settings from `hms`
3. **Fill in the settings** it asks for (§3.3). At minimum: `DATABASE_URL`, `TENANT_BASE_DOMAIN`, `PLATFORM_DOMAINS` and the `EMAIL_*` settings. `SECRET_KEY` is generated for you.
4. **Domains.** In the `hms` service → *Settings → Custom Domains*, add `yourdomain.com` and `*.yourdomain.com`. Create the DNS records Render shows at your domain registrar. HTTPS certificates follow automatically.
5. **Deploy.** Each deploy builds the web app and runs `migrate`, `setup_platform` and `process_signups` before going live. The health check is `/api/health/`.
6. **Create your operator account.** In the `hms` service's *Shell* tab, run `python manage.py createsuperuser`. Sign in at `yourdomain.com/operator`.
7. **Moving from the old single-hospital version** (once only): in the Shell, run
   ```bash
   python manage.py create_hospital --name "Main Hospital" --schema main --admin-email you@example.com
   python manage.py adopt_legacy_data --schema main --force
   python manage.py revoke_patient_privileges
   ```
8. **Payments.** Set `PAYSTACK_SECRET_KEY` (test key first). In Paystack's dashboard, set the webhook URL to `https://yourdomain.com/api/v1/platform/billing/paystack/webhook/`. Set your prices in the admin (*Plan prices*), then run `python manage.py sync_paystack_plans` in the Shell.
9. **Check readiness.** In the Shell, run:
   ```bash
   python manage.py launch_check --email you@example.com --sms +2348030000000
   ```
   Fix every ✗ and review every !. It sends a test email and SMS to confirm both really work.
10. **Smoke test:** sign up a test hospital at `yourdomain.com/signup`, run a patient through end to end, check that one hospital can't see another's data, then delete the test hospital. The full list is in [LAUNCH_PLAN.md](LAUNCH_PLAN.md).

After that, every push to `master` deploys automatically. To deploy only once CI has passed, set the `hms` service's *Auto-Deploy* to **After CI Checks Pass** (*Settings → Build & Deploy*). This is recommended.

### 3.3 Settings

Set these on the `hms` service (*Environment*). The cron job reads them from there. Every setting is also listed, with defaults, in [.env.example](../.env.example).

| Setting | Needed | What it does |
|---|---|---|
| `DATABASE_URL` | yes | Postgres internal URL |
| `SECRET_KEY` | yes (generated) | Signs sessions and tokens. Never share it |
| `TENANT_BASE_DOMAIN` | yes | `yourdomain.com`: hospitals live at `<name>.yourdomain.com` |
| `PLATFORM_DOMAINS` | yes | `yourdomain.com`: the platform site (Render's own hostname is added automatically) |
| `PRODUCT_NAME` | recommended | Your product's name on the website, emails and admin (default `HMS`) |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | yes | SMTP login from your email provider |
| `DEFAULT_FROM_EMAIL` | yes | e.g. `HMS <no-reply@yourdomain.com>` (verify the domain with the provider) |
| `PAYSTACK_SECRET_KEY` | to take card payments | `sk_test_...`, then `sk_live_...` |
| `SENTRY_DSN`, `SENTRY_FRONTEND_DSN` | recommended | Error reports (Django and React projects) |
| `SMS_BACKEND`, `SMS_API_KEY`, `SMS_SENDER_ID` | for patient SMS | `termii` or `africastalking`. Add `SMS_USERNAME` for Africa's Talking |
| `ADMIN_URL` | recommended | Hide the admin, e.g. `staff-portal-8f3a/` |
| `SUBSCRIPTION_TRIAL_DAYS`, `SUBSCRIPTION_GRACE_DAYS` | optional | Default 14 and 7 |
| `SMS_MONTHLY_LIMIT_PER_HOSPITAL`, `SMS_REMINDER_HOUR` | optional | Default 500 per month, at 9:00 hospital time |
| `THROTTLE_*`, `JWT_*`, `LOGIN_*` | optional | Security tuning (defaults in .env.example) |

### 3.4 Scheduled jobs

`hms-reminders` runs `python manage.py run_hourly` every hour. That does two things:
- **SMS reminders** for tomorrow's appointments, sent once each hospital's morning reaches `SMS_REMINDER_HOUR`
- **Notices to hospital admins:** the trial ends in 7, 3 or 1 days, payment is overdue, or records are read-only

Each runs once per item, so extra runs are harmless. Check it in Render → `hms-reminders` → *Logs*.

---

## 4. Running it day to day

### 4.1 Deploying changes
Push to `master`. Render builds and deploys, after CI passes if you turned that on (§3.2). Migrations run before the new version takes traffic. If a deploy fails, Render keeps the previous version running.

### 4.2 Adding hospitals
- **Self-serve:** hospitals sign up at `yourdomain.com/signup` and are ready within a minute of confirming their email.
- **By you:** in the operator dashboard or the API, or in the Shell: `python manage.py create_hospital --name "..." --schema ... --admin-email ...`
- If a signup gets stuck, the operator dashboard (*Signups*) has **Retry**, and every deploy finishes interrupted ones.

### 4.3 Money
- **Payments** show in the operator dashboard. **Bank transfers:** open the hospital → *Record a bank transfer*.
- **Changing prices:** edit them in the admin, then run `python manage.py sync_paystack_plans --reprice`.
- **Goodwill or trial extensions:** open the hospital → *Give extra days*.

### 4.4 Watching it
- **Sentry:** errors, with no patient data.
- **Render logs:** JSON lines. Every line and error response carries a request id, so you can match them up.
- `python manage.py launch_check` any time something seems off.
- `python manage.py database_report`: row counts per hospital.

### 4.5 Backups
See [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md):
- Render keeps automatic backups.
- Take a manual backup (`scripts/backup.sh`) before risky changes.
- Run the restore drill (`scripts/restore_drill.sh`) monthly.

### 4.6 Legal text
Admin → *Terms and privacy*: add the new version, untick *draft*, then use the **Publish** action. Published versions are locked.

### 4.7 A hospital leaves or asks for its data
- Admins can download everything from *Settings → Export all records*.
- You can export on their behalf: `python manage.py export_hospital --schema <name> --output file.zip`.
- To stop access, suspend the hospital in the operator dashboard. Nothing is deleted.

### 4.8 All commands
The full list is in the README's [management commands](../README.md#multi-tenancy) table. The ones you'll use most: `launch_check`, `create_hospital`, `sync_paystack_plans`, `export_hospital`, `process_signups`, `database_report`, `createsuperuser`.

---

## 5. Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| `main.localhost` doesn't open | The servers aren't running (§2.3), or you used port 8000 for the web app: use **5173** for the app, **8000** for the API |
| 404 at a hospital's address | No hospital has that address. Check the spelling, or `Domain` in the admin |
| "Port already in use" | Another server is running. Close it, or start on another port: `runserver 8001` and `npm run dev -- --port 5174` |
| `password authentication failed` on startup | `DB_*` in `.env` doesn't match your Postgres login |
| Migrations missing after pulling changes | `python manage.py migrate` (and `pip install -r requirements-dev.txt`, `npm install` if dependencies changed) |
| Emails don't arrive (production) | `launch_check --email you@...`; check SPF/DKIM for your domain with the provider; check spam |
| Hospital's changes refused with 402 | Its subscription lapsed (read-only). Pay, or *Give extra days* in the operator dashboard |
| Signup stuck on "Setting up" | Operator dashboard → *Signups* → **Retry**, or `python manage.py process_signups` |
| SMS not sent | `launch_check --sms <number>`; the hospital switched SMS on in *Settings*; the patient has a mobile number and hasn't opted out; the monthly cap |
| Reminders not going out | `hms-reminders` logs in Render; `SMS_REMINDER_HOUR` hasn't been reached yet in the hospital's time zone |
| Paystack payment didn't extend access | Webhook URL in Paystack; the payment appears in the hospital's payment history; record it manually if needed |
