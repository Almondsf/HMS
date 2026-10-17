# HMS: User Stories

A user story describes one thing a person needs from the software, in their own terms:

> **As a** *(who)*, **I want** *(what)*, **so that** *(why)*.

Each story has **acceptance criteria**: the checks that must be true for the story to count as done. They double as a test plan. For what the app is and how it's built, see [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md).

**Status:** ✅ built · 🔜 planned (not built yet)

Story ids (e.g. `FD-3`) are stable, so issues, commits and tests can refer to them.

---

## Contents

1. [Everyone who signs in](#1-everyone-who-signs-in-acc)
2. [Front desk (receptionist)](#2-front-desk-fd)
3. [Nurse](#3-nurse-nur)
4. [Doctor](#4-doctor-doc)
5. [Lab technician](#5-lab-technician-lab)
6. [Pharmacist](#6-pharmacist-pha)
7. [Cashier](#7-cashier-cas)
8. [Hospital admin](#8-hospital-admin-adm)
9. [Patient](#9-patient-pat)
10. [Platform operator](#10-platform-operator-plt)
11. [Hospital owner deciding to buy](#11-prospective-hospital-buy)
12. [Non-functional stories](#12-non-functional-stories-nfr)

---

## 1. Everyone who signs in (ACC)

**ACC-1 ✅ Sign in**
As a staff member, I want to sign in with my email and password, so that I can reach the screens for my job.
- Sign-in only works at my own hospital's address; my account and token are useless at another hospital.
- After too many wrong passwords my account is locked for a while, and the attempt is logged as a security event.
- I land on a dashboard and only see the menu items my role and my hospital's plan allow.

**ACC-2 ✅ Stay signed in safely**
As a staff member, I want my session to survive a page reload but not be stealable, so that I'm not signing in all day and nobody can hijack my account.
- Reloading the page keeps me signed in.
- No token is stored where page scripts can read it (localStorage, sessionStorage or readable cookies).
- Signing out ends the session on the server, not just in the browser.

**ACC-3 ✅ Forgot my password**
As a staff member who forgot my password, I want to reset it by email, so that I don't have to wait for an admin.
- The page gives the same answer whether or not my email has an account.
- The link works once and expires after an hour.
- Setting a new password signs me out everywhere else.

**ACC-4 ✅ Change my password**
As a staff member, I want to change my password, so that I can keep my account secure.
- I must enter my current password.
- Weak or common passwords are refused with a reason.

**ACC-5 ✅ Forced change after an admin reset**
As a staff member given a temporary password, I want to be made to choose my own at next sign-in, so that the admin doesn't know my password.
- Until I change it, every screen redirects me to "Change password".

**ACC-7 ✅ Two-factor sign-in**
As an administrator (or anyone handling sensitive records), I want my account to need a code from my phone as well as my password, so that a stolen password alone can't open it.
- I set it up by scanning a QR code with an authenticator app, and get 10 single-use recovery codes.
- Each code works once, and guessing codes leads to account lockout.
- Platform operators and hospital admins must use it. Other staff can choose to.
- If I lose my phone, I use a recovery code, or another admin resets it.

**ACC-6 ✅ Know what needs me**
As a staff member, I want to be notified when something needs me (a patient waiting, results ready, a prescription to fill, a patient ready to pay), so that nothing waits because nobody noticed.
- A bell in the header shows how many unread notifications I have, updated every 30 seconds.
- Opening a notification marks it read and takes me to the right screen.
- Urgent ones (emergencies, critical vitals) stand out.
- I'm never notified about something I just did myself.

---

## 2. Front desk (FD)

**FD-1 ✅ Register a patient**
As a receptionist, I want to register a new patient quickly, so that they can be seen without a long wait.
- A medical record number (e.g. `SLH-000124`) is assigned automatically and never changes.
- Two receptionists registering at the same moment never get the same number.
- Email and password are optional; most patients never sign in.
- I can enter an existing paper record number instead, and it's kept.

**FD-2 ✅ Find a patient**
As a receptionist, I want to search patients by any part of their name, number, phone or email, so that I don't create duplicates.
- "ada obi" finds "Adaeze Obi"; every word must match something.
- Each search of patient records is captured in the audit trail.

**FD-3 ✅ Book an appointment**
As a receptionist, I want to book a patient with a doctor at a time, so that the doctor's day is planned.
- A doctor can't be double-booked, and neither can a patient, even if two people book at the same instant.
- Inactive doctors can't be booked.
- I can reschedule, cancel or mark a no-show.

**FD-4 ✅ Check a patient in**
As a receptionist, I want to check in a patient when they arrive, so that they join the doctor's queue.
- Only works on the day of the appointment.
- Opens a visit in "waiting" and starts the patient's invoice, charging any automatic fees (e.g. card fee).

**FD-5 ✅ Walk-in visit**
As a receptionist, I want to open a visit for a patient without an appointment, so that walk-ins are handled the same way.

**FD-6 ✅ Cancel a visit**
As a receptionist, I want to cancel a visit if the patient leaves before being seen, so that the queue stays accurate.
- Only possible while the patient is still waiting.

**FD-7 ✅ Record insurance cover**
As a receptionist, I want to record a patient's HMO/NHIA membership, so that the cashier can bill the insurer. *(Pro plan)*
- Member number, provider, validity dates and optional coverage %.

**FD-8 ✅ See today's queue**
As a receptionist, I want to see who is waiting for which doctor and for how long, so that I can answer patients' questions.

**FD-9 ✅ Take a payment**
As a receptionist at a small clinic without a cashier, I want to record payments, so that patients can pay at the front desk.

**FD-11 ✅ Bring in our existing patients**
As a receptionist at a clinic moving from paper or Excel, I want to import our patient list, so that we don't retype hundreds of records.
- I can upload an Excel or CSV file with our own column names (Surname, DOB, Card number...).
- I see every problem by row and column before anything is saved, including likely duplicates of patients already registered.
- I can import everything once it's clean, or just the good rows.
- Existing record numbers are kept; patients without one get a new number.

**FD-10 ✅ SMS reminders**
As a receptionist, I want patients to get an SMS reminder before their appointment, so that fewer people miss them.
- The admin switches on booking confirmations and day-before reminders in Settings.
- Patients who asked not to get SMS (a tick on their record), or who have no valid mobile number, are skipped, and the reason is recorded.
- Each reminder is sent once. A rescheduled appointment gets a new confirmation and a new reminder.
- The front desk can see what was sent to a patient (`/api/v1/sms-messages/?patient=`).

---

## 3. Nurse (NUR)

**NUR-1 ✅ Triage**
As a triage nurse, I want to set each waiting patient's urgency, so that the sickest are seen first.
- Levels: emergency, urgent, standard, non-urgent.
- The queue reorders by urgency, then arrival time.
- Marking an emergency raises an `emergency_arrival` event.

**NUR-2 ✅ Record vital signs**
As a nurse, I want to record vital signs, so that the doctor has them before the consultation.
- Every measurement is optional.
- Impossible values (e.g. temperature 400 °C) are rejected as typos.
- BMI is calculated, abnormal values are flagged, and critical readings are highlighted and raise an event.
- Readings can't be edited; a correction is a new reading, so the history is honest.

**NUR-3 ✅ See vital sign history**
As a nurse or doctor, I want to see a patient's earlier readings, so that I can spot trends.

---

## 4. Doctor (DOC)

**DOC-1 ✅ My queue**
As a doctor, I want to see only my patients for today in priority order, so that I know who to call next.

**DOC-2 ✅ Call a patient in**
As a doctor, I want to start a visit, so that the queue shows the patient is with me.
- Only the assigned doctor can start or complete the visit.

**DOC-3 ✅ Write consultation notes**
As a doctor, I want to write notes in SOAP format (subjective, objective, assessment, plan), so that the record is structured and complete.
- Recording a consultation automatically starts a waiting visit.
- The consultation fee is charged automatically, if the hospital set one.
- Only the assigned doctor can write the consultation.

**DOC-4 ✅ Diagnose with ICD-10**
As a doctor, I want to pick diagnoses from a searchable ICD-10 list, so that records and insurance claims use standard codes.
- Searching "malaria" or "b509" finds the right code.
- One primary diagnosis per consultation; others are secondary.
- Provisional diagnoses can later be confirmed or ruled out, never deleted.
- Free text is allowed when no code fits.

**DOC-5 ✅ Prescribe**
As a doctor, I want to prescribe drugs, so that the pharmacy can dispense them.
- The prescription appears in the pharmacy queue immediately.

**DOC-6 ✅ Order lab tests**
As a doctor, I want to order tests from the catalogue, so that the lab knows what to do. *(Pro plan)*
- The order appears in the lab work list, and each test is charged to the visit's invoice.

**DOC-7 ✅ See results**
As a doctor, I want to see lab results for my patients, so that I can act on them.
- I only see results for my own patients.

**DOC-8 ✅ Complete the visit**
As a doctor, I want to complete the visit, so that the patient leaves my queue.

---

## 5. Lab technician (LAB)

*(Pro plan)*

**LAB-1 ✅ Work list**
As a lab technician, I want a list of pending tests, so that I know what to do next.

**LAB-2 ✅ Process a test**
As a lab technician, I want to mark samples collected, enter results and complete tests, so that doctors get results quickly.
- Steps: pending → collected → in progress → completed.
- Completing a result raises an event (future: notify the doctor).

**LAB-3 ✅ Walk-in lab request**
As a lab technician, I want to register a test for a patient referred from outside, so that walk-in lab customers are served and billed.
- Walk-ins get their own invoice.

**LAB-4 ✅ Print a report**
As a lab technician, I want to print a lab report with the hospital's name, so that the patient or referring doctor gets a copy.

**LAB-5 ✅ Maintain the test catalogue**
As a lab technician, I want to add tests and set their prices, so that orders are billed correctly.

---

## 6. Pharmacist (PHA)

**PHA-1 ✅ Prescription queue**
As a pharmacist, I want to see prescriptions waiting to be dispensed, so that patients aren't kept waiting.

**PHA-2 ✅ Dispense**
As a pharmacist, I want to dispense against a prescription, so that stock and the patient's bill update together.
- I can dispense part of a prescription now and the rest later.
- I can never dispense more than was prescribed, or more than is in stock, even if a colleague dispenses at the same moment.
- Each dispensed drug is charged to the visit's invoice.

**PHA-3 ✅ Manage drugs and stock**
As a pharmacist, I want to maintain drugs, prices and stock levels, so that I know what I have and what it costs.
- Low-stock drugs are flagged and raise an event.

---

## 7. Cashier (CAS)

**CAS-1 ✅ See what a patient owes**
As a cashier, I want each visit's invoice to fill itself as care happens, so that I don't have to chase departments for charges.
- Charges are added automatically for visit fees, consultations, lab tests and drugs dispensed.
- Each source is charged exactly once.
- Unpriced items appear as ₦0 and flagged; care isn't blocked, but I must price them before issuing.

**CAS-2 ✅ Adjust and issue an invoice**
As a cashier, I want to add manual items, price flagged lines, void wrong lines with a reason and issue the invoice, so that the bill is correct before the patient pays.
- After issue, lines can't change.

**CAS-3 ✅ Take payment**
As a cashier, I want to record cash, card/POS, transfer or mobile money payments, so that the patient can leave.
- A double-click or two cashiers at once can never overpay an invoice.
- The invoice becomes "paid" when the balance reaches zero.

**CAS-4 ✅ Print a receipt**
As a cashier, I want to print a receipt, so that the patient has proof of payment.

**CAS-5 ✅ Bill an insurer**
As a cashier, I want to raise a claim to the patient's HMO, so that the hospital is paid for covered care. *(Pro plan)*
- The cover must belong to the patient and be valid on the date of service.
- Providers that require it need a pre-authorisation code.
- While the claim is open, the patient pays only their share.
- If the insurer rejects or pays less, the difference goes back to the patient.
- I can print a claim document with diagnoses and itemised charges.

**CAS-6 ✅ Chase insurers**
As a cashier, I want to see how much each insurer still owes, so that I can follow up.

**CAS-7 ✅ End-of-day summary**
As a cashier, I want a summary of money taken by method and by cashier, so that I can balance the till.

---

## 8. Hospital admin (ADM)

**ADM-1 ✅ Create staff accounts**
As an admin, I want to create accounts for doctors, nurses, lab techs, pharmacists, receptionists and cashiers, so that staff can use the system.

**ADM-2 ✅ Deactivate staff**
As an admin, I want to deactivate someone who has left, so that they lose access immediately.
- They are signed out everywhere.
- Their past records stay intact; accounts are never deleted.
- I can't deactivate myself.

**ADM-3 ✅ Reset a staff password**
As an admin, I want to give a locked-out staff member a temporary password, so that they can get back to work.
- The temporary password is shown once.
- The account is unlocked and must choose a new password at next sign-in.

**ADM-4 ✅ Set up the hospital**
As an admin, I want to manage departments, fees (tariff), insurers and settings (name, contact details, timezone, currency, record-number prefix), so that the system matches how we work.

**ADM-5 ✅ Reports**
As an admin, I want clinical, financial, pharmacy and lab reports for any period, so that I can run the hospital well.
- Includes waiting times, top diagnoses, income, receivables aging, stock value and lab turnaround.

**ADM-6 ✅ Who looked at this record?**
As an admin, I want to see everyone who viewed or changed a patient's record, so that I can investigate complaints and meet data-protection law.
- Every read and change is recorded with who, when and from where.
- Nobody, including admins, can edit or delete audit entries.

**ADM-10 ✅ Take our data with us**
As an admin, I want to download all our records, so that we have our own copy and could move to another system.
- One ZIP of CSV files that open in Excel, covering patients, visits, results, prescriptions, invoices and more.
- I must enter my password, and the export is recorded in the audit log.
- It works even when our subscription has lapsed.

**ADM-7 ✅ Pay for the subscription**
As an admin, I want to pay for our plan online, monthly or yearly, so that the hospital keeps full access.
- Payment is by Paystack; renewal is automatic.
- I can see our status, renewal date and payment history.
- I can stop automatic renewal; access continues until the paid period ends.

**ADM-8 ✅ Be warned before access is limited**
As an admin, I want clear warnings when payment is due or overdue, so that we're never caught out.
- A banner shows near the end of the trial, during the grace period and when read-only.
- Other staff see the banner too and are told to inform an admin.

**ADM-9 ✅ Never lose access to records**
As an admin of a hospital whose subscription lapsed, I want staff to still view records, so that patient care isn't endangered.
- Viewing, signing in and paying always work; only saving new data is blocked.

---

## 9. Patient (PAT)

**PAT-1 ✅ My record is private**
As a patient, I want my record seen only by staff who need it, and every access logged, so that my privacy is protected.

**PAT-2 ✅ See my own visits and bills (API)**
As a patient with a login, I want to see my own visits and invoices, so that I know what I was treated for and what I owe.
- I only ever see my own data.
- Available through the API today; there is no patient app yet.

**PAT-3 🔜 Patient app**
As a patient, I want a simple web or mobile app for appointments, results and bills, so that I don't have to call the hospital.

---

## 10. Platform operator (PLT)

**PLT-1 ✅ Onboard a hospital**
As the platform operator, I want to create a hospital with its address and first admin, so that a new customer can start immediately.
- The hospital gets its own isolated database schema.
- A one-time admin password is returned if I didn't set one.
- The hospital starts on a 14-day free trial.

**PLT-2 ✅ Manage hospitals**
As the platform operator, I want to list hospitals, change plans and suspend a hospital, so that I can run the business.
- Suspending blocks all access without deleting any data.

**PLT-3 ✅ Set prices**
As the platform operator, I want to edit plan prices, so that I can change pricing without a code change.
- After a price change I can re-sync plans to Paystack.

**PLT-4 ✅ Record a bank transfer**
As the platform operator, I want to record a payment made by bank transfer, so that hospitals without cards can pay.
- The same transfer reference can't be recorded twice.

**PLT-5 ✅ Trustworthy payments**
As the platform operator, I want every payment verified with Paystack and every webhook signature checked, so that nobody gets free access by faking a payment.

**PLT-6 ✅ Platform dashboard**
As the platform operator, I want web screens showing hospitals, trials ending, overdue payments and revenue, so that I don't need the API or Django admin.
- The overview shows monthly recurring revenue, money collected per month, and hospitals by state.
- "Needs attention" lists trials ending this week, overdue hospitals and lapsed hospitals.
- Each hospital shows its usage (staff, patients, recent visits, last activity), so I can spot hospitals that signed up but never started.
- From a hospital I can give extra days, record a bank transfer, change its plan, or suspend it.
- I can see every signup and retry one that failed.
- Only platform superusers can open it.

**PLT-7 ✅ Switch email and SMS providers**
As the platform operator, I want to choose and switch the companies that deliver our email and SMS without a deploy, so that I can react to outages, prices or deliverability problems.
- I enter a provider's keys once; they are stored encrypted and never shown again.
- I can send a test message and see the provider's own error if it fails.
- Switching only works after a successful test, so a typo can't silently stop emails or reminders.
- I can also switch with an API call (`PUT /api/v1/platform/providers/<email|sms>/`).

---

## 11. Prospective hospital (BUY)

**BUY-1 ✅ Self-serve signup**
As a hospital owner, I want to sign up on the website and start a free trial myself, so that I can try the product without talking to sales.
- I choose the hospital's name, its web address and a plan, and set my own admin password.
- As I type, the form tells me whether the address is free.
- Nothing is created until I confirm my email; then the hospital is ready within about a minute and I can sign in.
- Spam and abuse are limited: email verification, rate limits, a hidden bot trap and reserved addresses.

**BUY-3 ✅ See what it costs**
As a hospital owner, I want a public page explaining the product and its prices, so that I can decide before signing up.

**BUY-4 ✅ Find my hospital**
As a staff member who only remembers "HMS", I want to reach my hospital's sign-in page from the main website, so that I don't need the exact link.

**BUY-5 ✅ Know what I'm agreeing to**
As a hospital owner, I want to read the terms and privacy policy before signing up, so that I know how our patients' data is handled.
- Signup can't be completed without accepting them, and the versions accepted are recorded.
- A draft document is clearly labelled as a draft.

**BUY-2 ✅ Choose a plan that fits**
As a small clinic owner, I want a cheaper plan without lab and insurance, so that I only pay for what I use.

---

## 12. Non-functional stories (NFR)

These are about qualities rather than features. They apply everywhere.

**NFR-1 ✅ Hospitals are isolated**
As a hospital, I want certainty that no other hospital can ever see our data.
- Separate database schema per hospital; tokens are bound to their hospital; tested automatically.

**NFR-2 ✅ Nothing medical disappears**
As a hospital, I want medical and financial history never to be silently deleted.
- Records are voided, ruled out or deactivated instead; database constraints prevent deletes.

**NFR-3 ✅ Correct under pressure**
As a busy hospital, I want simultaneous actions (bookings, payments, dispensing, registrations) never to corrupt data.
- Row locks and transactions on every race-prone path.

**NFR-4 ✅ Errors are traceable**
As a support engineer, I want every error to carry a request id that matches logs and audit entries, so that I can find the cause fast.
- Error reports to Sentry contain no patient data.

**NFR-5 ✅ Recoverable**
As the operator, I want tested backups and a written restore procedure, so that a disaster isn't the end of the business.

**NFR-6 ✅ Quality gate**
As a developer, I want every push checked by lint, tests (≥85% coverage), a dependency audit, a frontend build and a Docker boot, so that broken code doesn't reach hospitals.

**NFR-7 ✅ Works on a phone**
As staff using a phone or tablet, I want the web app to work on small screens, so that I'm not tied to a desk.
