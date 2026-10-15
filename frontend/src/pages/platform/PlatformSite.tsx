/**
 * The platform site (the bare domain, e.g. hms.app): what the product is, prices,
 * self-serve signup, and a way to find your hospital's own address.
 */
import {
  ArrowRight,
  Check,
  FlaskConical,
  Lock,
  Pill,
  Receipt,
  ShieldCheck,
  Stethoscope,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { lazy, Suspense, useState, type FormEvent } from 'react'
import { Link, Navigate, Outlet, Route, Routes } from 'react-router'

import { usePlans } from '@/api/signup'
import { Button, Card, Input, Spinner } from '@/components/ui'
import { formatMoney } from '@/lib/hospital'
import { hospitalAppUrl, productName, tenantBaseDomain } from '@/lib/tenant'

import { PLANS } from './plans'
import { SignupPage, VerifySignupPage } from './SignupPages'

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-lg bg-brand-500 text-white" aria-hidden>
        <svg viewBox="0 0 24 24" className="size-5" fill="currentColor">
          <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" />
        </svg>
      </span>
      <span className="font-semibold text-slate-900">{productName()}</span>
    </Link>
  )
}

// The operator dashboard is only for platform staff: keep it out of visitors' downloads
const OperatorApp = lazy(() => import('./operator/OperatorApp').then((module) => ({ default: module.OperatorApp })))

function SiteLayout() {
  return (
    <div className="flex min-h-full flex-col bg-white">
      <header className="border-b border-slate-100">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-2 sm:gap-4">
            <Link
              to="/sign-in"
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:text-brand-700"
            >
              Sign in
            </Link>
            <Link
              to="/signup"
              className="rounded-lg bg-brand-500 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-600"
            >
              Start free trial
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-slate-100 py-8 text-center text-sm text-slate-500">
        © {new Date().getFullYear()} {productName()} · Hospital management for clinics and hospitals
      </footer>
    </div>
  )
}

const FEATURES: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: Users,
    title: 'Front desk & queue',
    text: 'Register patients in seconds, book appointments without double-booking, and see who is waiting.',
  },
  {
    icon: Stethoscope,
    title: 'Consultations',
    text: 'Triage and vitals, structured notes, ICD-10 diagnoses, prescriptions and lab orders in one place.',
  },
  {
    icon: FlaskConical,
    title: 'Laboratory',
    text: 'A live work list, results entry and printable reports with your logo.',
  },
  { icon: Pill, title: 'Pharmacy', text: 'Dispense against prescriptions with stock that can never be oversold.' },
  {
    icon: Receipt,
    title: 'Billing that fills itself',
    text: 'Every service is charged as it happens, so nothing slips through. Receipts and a daily cash summary.',
  },
  {
    icon: ShieldCheck,
    title: 'HMO & NHIA claims',
    text: 'Patients pay only their share; track what every insurer owes.',
  },
]

function Pricing() {
  const { data } = usePlans()
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {PLANS.map(({ plan, summary, includes }) => {
        const price = data?.prices.find((item) => item.plan === plan && item.interval === 'monthly')
        return (
          <Card key={plan} className={plan === 'pro' ? 'flex flex-col p-6 ring-2 ring-brand-500' : 'flex flex-col p-6'}>
            <h3 className="font-semibold capitalize text-slate-900">{plan}</h3>
            <p className="mt-1 text-sm text-slate-500">{summary}</p>
            <p className="mt-4">
              <span className="text-3xl font-semibold text-slate-900">
                {price ? formatMoney(price.amount, price.currency).replace(/\.00$/, '') : '…'}
              </span>
              <span className="text-sm text-slate-500"> / month</span>
            </p>
            <ul className="mt-4 flex-1 space-y-2 text-sm text-slate-600">
              {includes.map((item) => (
                <li key={item} className="flex gap-2">
                  <Check className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden />
                  {item}
                </li>
              ))}
            </ul>
            <Link
              to={`/signup?plan=${plan}`}
              className="mt-6 rounded-lg border border-brand-200 px-4 py-2 text-center text-sm font-medium text-brand-700 hover:bg-brand-50"
            >
              Try {plan} free
            </Link>
          </Card>
        )
      })}
    </div>
  )
}

function LandingPage() {
  const { data } = usePlans()
  const trialDays = data?.trial_days ?? 14
  return (
    <>
      <section className="bg-gradient-to-b from-brand-50 to-white">
        <div className="mx-auto max-w-6xl px-4 py-16 text-center sm:px-6 sm:py-24">
          <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
            Run your whole hospital in one place
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
            Patients, appointments, consultations, lab, pharmacy, billing and HMO claims, built for clinics and
            hospitals in Nigeria. Set up in minutes, on any computer or phone.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-3 font-medium text-white shadow-sm hover:bg-brand-600"
            >
              Start your {trialDays}-day free trial <ArrowRight className="size-4" aria-hidden />
            </Link>
            <a
              href="#pricing"
              className="rounded-lg border border-slate-200 bg-white px-5 py-3 font-medium text-slate-700 hover:bg-slate-50"
            >
              See pricing
            </a>
          </div>
          <p className="mt-3 text-sm text-slate-500">No card needed for the trial.</p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title}>
              <div className="mb-3 inline-flex rounded-lg bg-brand-50 p-2.5 text-brand-600">
                <Icon className="size-5" aria-hidden />
              </div>
              <h3 className="font-medium text-slate-900">{title}</h3>
              <p className="mt-1 text-sm text-slate-600">{text}</p>
            </div>
          ))}
        </div>
        <Card className="mt-12 flex flex-col gap-3 p-6 sm:flex-row sm:items-center">
          <Lock className="size-6 shrink-0 text-brand-600" aria-hidden />
          <p className="text-sm text-slate-600">
            <span className="font-medium text-slate-900">Private by design.</span> Each hospital's records are kept in
            their own separate database, and every view of a patient's record is logged, so you can always see who
            looked.
          </p>
        </Card>
      </section>

      <section id="pricing" className="bg-slate-50/70 py-16">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <h2 className="text-center text-2xl font-semibold text-slate-900">Simple monthly pricing</h2>
          <p className="mb-10 mt-2 text-center text-slate-600">
            Every plan starts with a {trialDays}-day free trial. Pay yearly and get two months free.
          </p>
          <Pricing />
        </div>
      </section>
    </>
  )
}

/** People who already have a hospital: send them to its own address. */
function FindHospitalPage() {
  const [address, setAddress] = useState('')
  const clean = address.trim().toLowerCase()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (clean) window.location.assign(hospitalAppUrl(clean, '/login'))
  }

  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="text-2xl font-semibold text-slate-900">Sign in to your hospital</h1>
      <p className="mt-2 text-sm text-slate-600">
        Each hospital has its own address. Enter yours to go to its sign-in page.
      </p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <Input
          label="Hospital address"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          placeholder="st-lukes"
          autoCapitalize="none"
          autoCorrect="off"
          required
          hint={clean ? `${clean}.${tenantBaseDomain()}` : `yourhospital.${tenantBaseDomain()}`}
        />
        <Button type="submit" className="w-full">
          Continue
        </Button>
      </form>
      <p className="mt-6 text-sm text-slate-600">
        Not on {productName()} yet?{' '}
        <Link to="/signup" className="font-medium text-brand-600 hover:text-brand-700">
          Start a free trial
        </Link>
      </p>
    </div>
  )
}

export function PlatformSite() {
  return (
    <Routes>
      <Route
        path="operator/*"
        element={
          <Suspense fallback={<Spinner />}>
            <OperatorApp />
          </Suspense>
        }
      />
      <Route element={<SiteLayout />}>
        <Route index element={<LandingPage />} />
        <Route path="signup" element={<SignupPage />} />
        <Route path="signup/verify" element={<VerifySignupPage />} />
        <Route path="sign-in" element={<FindHospitalPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
