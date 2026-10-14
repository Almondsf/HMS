import type { Hospital } from '@/lib/hospital'

/** What each plan offers, for the landing and signup pages (prices come from the API). */
export const PLANS: { plan: Hospital['plan']; summary: string; includes: string[] }[] = [
  {
    plan: 'basic',
    summary: 'For clinics getting started',
    includes: [
      'Patients, appointments & queue',
      'Consultations, triage & vitals',
      'Pharmacy & stock',
      'Billing & receipts',
    ],
  },
  {
    plan: 'pro',
    summary: 'For hospitals with a lab and HMO patients',
    includes: ['Everything in Basic', 'Laboratory & printable reports', 'HMO / NHIA claims', 'Management reports'],
  },
  {
    plan: 'enterprise',
    summary: 'For larger hospitals',
    includes: ['Everything in Pro', 'Priority support', 'Help moving your records in'],
  },
]
