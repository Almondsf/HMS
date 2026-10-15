# HMS: Launch Plan

The route from "built" to "hospitals paying for it", in order. Tick items off as they're done.

**Who does what:** 🧑 you (accounts, money, decisions, real-world tasks) · 🤖 Claude (code) · 🤝 together

Stages 1 and 2 run **in parallel**: you set up the accounts while the code is finished. Stage 3 starts when both are done.

```
Stage 1  Get live (🧑)          ─┐
                                 ├─▶ Stage 3  Pilot with 2-3 hospitals ─▶ Stage 4  Grow
Stage 2  Finish the code (🤖)   ─┘
```

---

## Decisions to make first 🧑

These block other steps, so settle them early.

- [ ] **Product name.** "HMS" is a placeholder; the name appears on the landing page and in every email.
- [ ] **Domain**, e.g. `yourbrand.com` or `yourbrand.ng`. Hospitals get `<name>.yourdomain`.
- [ ] **Prices** for Basic, Pro and Enterprise (monthly; yearly is 10× by default). Talk to two or three clinic owners about what they pay today.
- [ ] **Email provider:** Brevo (free for 300 emails/day) is the easiest start.
- [ ] **SMS provider:** Termii or Africa's Talking. Only needed for Stage 2's SMS reminders.
- [ ] **Terms of service and privacy policy wording.** A Nigerian lawyer, or a reputable template adapted to the NDPA (Nigeria Data Protection Act). You handle patient data, so this matters.

---

## Stage 1: Get live 🧑

Detailed steps are in the [README](../README.md#deploying-render); this is the checklist.

### 1.1 Domain and hosting
- [ ] Buy the domain.
- [ ] **Back up the existing Render database** (`scripts/backup.sh`, or a manual backup in the Render dashboard).
- [ ] Render → *New → Blueprint* → this repository. Set `DATABASE_URL`, `TENANT_BASE_DOMAIN` and `PLATFORM_DOMAINS`.
- [ ] Add `yourdomain` and `*.yourdomain` to the service, and create the DNS records Render shows.
- [ ] In the Render Shell, run the upgrade commands once:
  ```bash
  python manage.py create_hospital --name "Main Hospital" --schema main --admin-email you@example.com
  python manage.py adopt_legacy_data --schema main --force
  python manage.py revoke_patient_privileges
  ```
- [ ] Check that Render's backup retention on your database plan is acceptable (how many days back you can restore).

### 1.2 Email
- [ ] Create the Brevo (or other) account and **verify your domain** (SPF/DKIM records), so emails don't land in spam.
- [ ] Set `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL` on Render.
- [ ] Test it: use "Forgot password?" on a hospital and confirm the email arrives.

### 1.3 Error monitoring
- [ ] Create a free Sentry account with two projects (Django and React).
- [ ] Set `SENTRY_DSN` and `SENTRY_FRONTEND_DSN` on Render.

### 1.4 Payments
- [ ] Create a Paystack account. Business verification needs your CAC registration documents and can take a few days, so **start early**.
- [ ] Set `PAYSTACK_SECRET_KEY` to the **test** key (`sk_test_...`) first.
- [ ] Paystack dashboard → *Settings → API Keys & Webhooks*: set the webhook URL to `https://yourdomain/api/v1/platform/billing/paystack/webhook/`.
- [ ] Set your real prices in the platform admin (*Plan prices*), then run `python manage.py sync_paystack_plans`.
- [ ] Pay for a plan with a Paystack **test card** and check the subscription updates.
- [ ] When verified, switch to the live key (`sk_live_...`) and run `sync_paystack_plans` again.

### 1.5 Production smoke test 🤝
- [ ] Sign up a test hospital at `yourdomain/signup`. The verification and welcome emails arrive, and you can sign in.
- [ ] Run one patient through: register → book → check in → triage → consult → lab → pharmacy → invoice → payment → receipt.
- [ ] Confirm one hospital can't see another's data: sign in to hospital A and try hospital B's address.
- [ ] Confirm a deliberate error shows up in Sentry.
- [ ] Delete the test hospital.

**Stage 1 is done when** the platform is live on your domain, email and payments work end to end, and the smoke test passes.

---

## Stage 2: Finish the code for launch 🤖

In this order:

### 2.1 Terms and privacy (needs your wording)
- [ ] Terms of service and privacy policy pages on the platform site.
- [ ] Signup requires ticking "I accept the terms", and the acceptance (version and date) is recorded.
- [ ] Links in the footer and in the signup emails.

### 2.2 Platform operator dashboard ✅
- [x] Web screens on the platform site for platform operators only (`/operator`).
- [x] Every hospital: plan, status, trial or renewal date, last activity.
- [x] Lists that need attention: trials ending this week, overdue payments, recent signups (including failed ones).
- [x] Revenue this month and per month, and monthly recurring revenue.
- [x] Actions: record a bank transfer, change plan, extend a trial, suspend or reactivate.

### 2.3 SMS appointment reminders (needs the SMS provider account)
- [ ] Reminder the day before each appointment, and optionally on booking.
- [ ] Per-hospital switch and sender name; opt-out for patients.
- [ ] A job that runs on a schedule (a Render cron job).
- [ ] Each SMS costs money: decide whether it's included in plans or charged per message.

### 2.4 Polish from your click-through 🤝
- [ ] Click through every screen as each role (the demo logins are in `DEMO_CREDENTIALS.md`) and note anything confusing. Each note becomes a fix.

**Stage 2 is done when** all of the above are merged with CI passing.

---

## Stage 3: Pilot with 2-3 hospitals 🤝

Real users find what tests can't. Start small, ideally clinics you can visit.

- [ ] **Recruit** 2-3 clinics, ideally one small (Basic) and one with a lab (Pro). Offer a discount or a free period in exchange for feedback.
- [ ] **Clinical review:** have a doctor check the vital-sign limits ([clinical/vitals.py](../clinical/vitals.py)) and the triage wording.
- [ ] **Load the full ICD-10 list** with `load_icd10`. Only about 45 common codes are loaded today; check the licence of the list you choose.
- [ ] **Onboard each one** in person or on a call: create staff accounts, set fees (tariff) and insurers, run their first patient together.
- [ ] **Moving records in:** if a pilot has existing patient records (spreadsheet or old system), plan an import. 🤖 can build an importer once there's a sample file.
- [ ] **Weekly check-in** with each pilot: what's slow, what's missing, what's confusing. Keep a list.
- [ ] **Watch Sentry** for errors, and fix them fast during the pilot.

**Stage 3 is done when** the pilots have used HMS daily for about a month, the top issues are fixed, and at least one is paying.

---

## Stage 4: Grow

Let the pilots decide the order. Likely candidates:

| Feature | Who it's for | Size |
|---|---|---|
| Data export (a hospital downloads all its records) | Everyone; it builds trust and is expected under the NDPA | Small |
| Records importer | New hospitals moving from paper, Excel or another system | Medium |
| Multi-branch (one group, several locations) | Hospital groups | Large |
| Custom domains (`portal.stlukes.com`) | Larger hospitals | Medium |
| Single sign-on | Large organisations | Medium |
| Patient app (appointments, results, bills) | Patients; a selling point for hospitals | Large |
| Inpatient care (wards, beds, admissions, nursing charts) | Hospitals with beds | Large |
| Move background work to a job queue | Needed when signups or SMS volume grow | Medium |

Marketing and sales 🧑: a demo video, a short case study from a pilot, and outreach to clinic owners and medical associations.

---

## Ongoing, after launch 🧑

| How often | What |
|---|---|
| Daily, during the pilot | Glance at Sentry |
| Weekly | Check signups, overdue payments and trials ending (in the dashboard, once built) |
| Monthly | **Restore drill**: `scripts/restore_drill.sh` ([BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md)) |
| Monthly | Update dependencies when CI's audit flags a vulnerability |
| Before risky changes | Manual backup (`scripts/backup.sh`) |
