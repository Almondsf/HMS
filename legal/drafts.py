# ruff: noqa: E501  (prose: one line per paragraph, as the page renders it)
'''
Starting drafts of the terms of service and privacy policy, seeded as
version "draft-1". NOT legal advice: they mark what such documents usually
cover, with [placeholders]. Have a Nigerian lawyer adapt and approve them,
then publish the approved text as a new version in the platform admin.
'''

TERMS = '''# Terms of Service

These terms are between [Company name] (RC [number]), of [registered address] ("we", "us"), and the hospital, clinic or organisation that signs up ("you"). By creating an account you accept them on behalf of your organisation, and you confirm you are authorised to do so.

## 1. The Service

We provide hospital management software as an online service (the "Service"): patient records, appointments, clinical notes, laboratory, pharmacy, billing, insurance claims and reports, as included in your plan. We may improve and change the Service; we will not remove a core feature of your plan without reasonable notice.

## 2. Accounts

- You are responsible for the accounts you create for your staff, for keeping passwords private, and for removing access when someone leaves.
- Tell us promptly at [support email] if you suspect unauthorised access.
- Only staff of your organisation may use your account.

## 3. Free trial and payment

- New accounts start with a free trial of the length shown at signup. No payment details are needed for the trial.
- After the trial, the Service is paid monthly or yearly in advance, at the prices shown when you pay. Payments are processed by Paystack or made by bank transfer.
- Subscriptions paid through Paystack renew automatically until you stop renewal in the app. Access continues until the end of the paid period.
- If a payment is overdue, the Service keeps working for a grace period. After it, your records become read-only: you can still view them, but not add or change them, until payment is made. We do this instead of locking you out, so patient care is never blocked.
- Prices may change; we will give at least [30] days' notice, and changes apply from your next renewal.
- Except where the law requires otherwise, payments are not refundable.

## 4. Your data

- You own the records you put into the Service. We use them only to provide the Service to you, as described in our Privacy Policy.
- For patient records, you are the data controller and we act as your data processor under the Nigeria Data Protection Act 2023. You are responsible for having a lawful basis to collect patient information and for informing patients.
- You can ask us for an export of your records at any time, including after you leave.
- After your account ends, we keep your records for [90] days so you can export them, then delete them, unless the law requires us to keep them longer.

## 5. Acceptable use

You must not misuse the Service, including by: trying to access another organisation's data; interfering with or overloading the Service; testing its security without our written permission; or using it for anything unlawful.

## 6. Availability and support

We aim to keep the Service available at all times but cannot promise it will be uninterrupted. We back up data regularly. Support is available at [support email] during [support hours].

## 7. Clinical responsibility

The Service is a record-keeping and administration tool. Clinical decisions remain the responsibility of your qualified staff. Flags and alerts (for example on vital signs) are aids, not medical advice.

## 8. Liability

To the extent the law allows, we are not liable for indirect or consequential losses, and our total liability in any 12 months is limited to the fees you paid us in that period. Nothing in these terms limits liability that cannot be limited by law.

## 9. Suspension and ending the agreement

- You can stop using the Service at any time by stopping renewal.
- We may suspend or end your access if you seriously breach these terms, after notice where reasonable.

## 10. Changes to these terms

We may update these terms. We will tell you about significant changes at least [30] days in advance. The version you accepted at signup is kept on record.

## 11. Law

These terms are governed by the laws of the Federal Republic of Nigeria. Disputes go to the courts of [Lagos State], unless we agree otherwise.

## 12. Contact

[Company name], [registered address], [contact email], [phone].
'''

PRIVACY = '''# Privacy Policy

This policy explains how [Company name] ("we", "us") handles personal information in connection with our hospital management software (the "Service"). It is written to meet the Nigeria Data Protection Act 2023 (NDPA).

## 1. Two kinds of information

- **Account information about our customers:** the names, email addresses and phone numbers of hospital staff and the people who sign up. For this we are the **data controller**.
- **Records that hospitals keep in the Service:** patient details, clinical notes, results, prescriptions and bills. For these the **hospital is the data controller** and we are its **data processor**: we handle them only on the hospital's instructions, to provide the Service. Patients with questions about their records should contact their hospital.

## 2. What we collect about customers

- Signup details: hospital name, your name, email, phone and password (stored only as a secure hash).
- Usage information needed to run and secure the Service: sign-in times, IP addresses, and a log of actions in the Service.
- Payment records: plans, amounts and references. Card details are handled by Paystack and never reach us.

## 3. Why we use it

To provide and secure the Service; to bill you; to contact you about your account, payments and important changes; and to meet legal obligations. Our lawful bases are performance of our contract with you, legitimate interests in running a secure service, and legal obligation.

## 4. How patient records are protected

- Each hospital's records are kept in a separate part of our database.
- Access is limited by staff role, and every view and change of a patient's record is logged. Hospitals can see who accessed a record.
- Connections are encrypted (HTTPS). Passwords are stored as secure hashes.
- Error reports sent to our monitoring service exclude patient information.
- We back up data regularly and test restoring it.

## 5. Who we share information with

Only service providers that help us run the Service, under contracts that protect the data:

- [Render] (hosting and database), [location of servers]
- [Paystack] (payments)
- [Email provider] (sending emails)
- [Sentry] (error monitoring; no patient information)
- [SMS provider] (appointment reminders, if the hospital turns them on)

We do not sell personal information. We disclose it to authorities only when the law requires.

## 6. International transfers

Some providers store data outside Nigeria. Where this happens, we rely on the safeguards the NDPA allows, such as adequate protection in the destination country or contractual protections.

## 7. How long we keep it

- Signup details that are never confirmed are deleted after 7 days.
- Hospital records are kept while the hospital uses the Service, then for [90] days so they can be exported, then deleted unless the law requires longer.
- Audit logs are kept for [period].

## 8. Your rights

Under the NDPA you can ask to access, correct or delete your personal information, object to or restrict its use, and receive a copy of it. Contact [data protection email]. For patient records, contact the hospital, and we will help it respond. You can also complain to the Nigeria Data Protection Commission.

## 9. Breaches

If a breach affects personal information, we will notify the affected hospitals and, where required, the Nigeria Data Protection Commission within the time the law requires.

## 10. Changes

We will post updates here and tell customers about significant changes.

## 11. Contact

[Company name], [registered address]. Data protection contact: [name, email].
'''
