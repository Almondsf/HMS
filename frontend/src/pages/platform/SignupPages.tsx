import { AlertCircle, CheckCircle2, Loader2, MailCheck } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'

import {
  useAvailability,
  usePlans,
  useSignup,
  useSignupProgress,
  useVerifySignup,
  type SignupDetails,
} from '@/api/signup'
import { Button, Card, cx, ErrorAlert, Input } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatMoney, type Hospital } from '@/lib/hospital'
import { productName, tenantBaseDomain } from '@/lib/tenant'

import { PLANS } from './plans'

/** "St. Luke's Hospital" -> "st-lukes-hospital": a suggested address. */
function toAddress(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/['’.]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^[^a-z]+/, '')
    .slice(0, 40)
    .replace(/-+$/, '')
}

function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])
  return debounced
}

function AddressStatus({ address }: { address: string }) {
  const checked = useDebounced(address)
  const { data, isFetching } = useAvailability(checked)
  const full = `${address || 'yourhospital'}.${tenantBaseDomain()}`

  if (address.length < 3 || checked !== address || isFetching || !data) {
    return <p className="text-xs text-slate-500">Your hospital's address: {full}</p>
  }
  return data.available ? (
    <p className="flex items-center gap-1.5 text-xs text-emerald-700">
      <CheckCircle2 className="size-3.5" aria-hidden /> {full} is available
    </p>
  ) : (
    <p className="flex items-center gap-1.5 text-xs text-red-600">
      <AlertCircle className="size-3.5" aria-hidden /> {data.reason}
    </p>
  )
}

function PlanPicker({ value, onChange }: { value: Hospital['plan']; onChange: (plan: Hospital['plan']) => void }) {
  const { data } = usePlans()
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-slate-700">Plan for your free trial</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {PLANS.map(({ plan, summary }) => {
          const price = data?.prices.find((item) => item.plan === plan && item.interval === 'monthly')
          return (
            <label
              key={plan}
              className={cx(
                'cursor-pointer rounded-lg border p-3 text-sm',
                value === plan
                  ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500'
                  : 'border-slate-200 hover:bg-slate-50',
              )}
            >
              <input
                type="radio"
                name="plan"
                value={plan}
                checked={value === plan}
                onChange={() => onChange(plan)}
                className="sr-only"
              />
              <span className="block font-medium capitalize text-slate-900">{plan}</span>
              <span className="block text-xs text-slate-500">{summary}</span>
              {price && (
                <span className="mt-1 block text-xs text-slate-700">
                  then {formatMoney(price.amount, price.currency).replace(/\.00$/, '')}/month
                </span>
              )}
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

export function SignupPage() {
  const [params] = useSearchParams()
  const initialPlan = PLANS.some(({ plan }) => plan === params.get('plan'))
    ? (params.get('plan') as Hospital['plan'])
    : 'pro'
  const [form, setForm] = useState<SignupDetails>({
    hospital_name: '',
    address: '',
    plan: initialPlan,
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    password: '',
    website: '',
  })
  // Suggest an address from the name until the person types their own
  const [addressEdited, setAddressEdited] = useState(false)
  const signup = useSignup()
  const { data: plans } = usePlans()
  const errors = signup.error instanceof ApiError ? signup.error.fieldErrors : {}

  const set = (field: keyof SignupDetails) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }))

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    signup.mutate({ ...form, email: form.email.trim(), address: form.address.trim() })
  }

  if (signup.isSuccess) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-brand-50 text-brand-600">
          <MailCheck className="size-6" aria-hidden />
        </div>
        <h1 className="text-2xl font-semibold text-slate-900">Check your email</h1>
        <p className="mt-3 text-slate-600">
          We sent a link to <span className="font-medium text-slate-900">{form.email}</span>. Open it to confirm your
          address, and we'll create {form.hospital_name} straight away.
        </p>
        <p className="mt-4 text-sm text-slate-500">
          The link works for 48 hours. Can't find it? Check your spam folder.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-2xl font-semibold text-slate-900">Start your free trial</h1>
      <p className="mt-2 text-slate-600">
        {plans?.trial_days ?? 14} days free, no card needed. You can choose to pay when the trial ends.
      </p>
      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        <Card className="space-y-4 p-5">
          <h2 className="font-medium text-slate-900">Your hospital</h2>
          <Input
            label="Hospital or clinic name"
            required
            value={form.hospital_name}
            error={errors.hospital_name}
            onChange={(event) => {
              const name = event.target.value
              setForm((current) => ({
                ...current,
                hospital_name: name,
                address: addressEdited ? current.address : toAddress(name),
              }))
            }}
          />
          <div className="space-y-1.5">
            <Input
              label="Web address"
              required
              minLength={3}
              maxLength={40}
              autoCapitalize="none"
              autoCorrect="off"
              value={form.address}
              error={errors.address}
              onChange={(event) => {
                setAddressEdited(true)
                setForm((current) => ({ ...current, address: event.target.value.toLowerCase() }))
              }}
            />
            {!errors.address && <AddressStatus address={form.address} />}
          </div>
          <PlanPicker value={form.plan} onChange={(plan) => setForm((current) => ({ ...current, plan }))} />
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="font-medium text-slate-900">You (the hospital's administrator)</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="First name"
              required
              autoComplete="given-name"
              value={form.first_name}
              onChange={set('first_name')}
              error={errors.first_name}
            />
            <Input
              label="Last name"
              required
              autoComplete="family-name"
              value={form.last_name}
              onChange={set('last_name')}
              error={errors.last_name}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Email"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={set('email')}
              error={errors.email}
              hint="You'll sign in with this"
            />
            <Input
              label="Phone (optional)"
              type="tel"
              autoComplete="tel"
              value={form.phone}
              onChange={set('phone')}
              error={errors.phone}
            />
          </div>
          <Input
            label="Password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={form.password}
            onChange={set('password')}
            error={errors.password}
            hint="At least 8 characters, not a common password"
          />
          {/* Hidden from people; bots that fill every field reveal themselves */}
          <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
            <label>
              Website
              <input type="text" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} />
            </label>
          </div>
        </Card>

        <ErrorAlert error={Object.keys(errors).length ? null : signup.error} />
        <div className="flex flex-col-reverse items-center justify-between gap-4 sm:flex-row">
          <p className="text-sm text-slate-600">
            Already on {productName()}?{' '}
            <Link to="/sign-in" className="font-medium text-brand-600 hover:text-brand-700">
              Sign in
            </Link>
          </p>
          <Button type="submit" loading={signup.isPending} className="w-full sm:w-auto">
            Create my hospital
          </Button>
        </div>
      </form>
    </div>
  )
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-md px-4 py-16 text-center">{children}</div>
}

/** The emailed link: confirm, then follow the hospital's setup until it is ready. */
export function VerifySignupPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const verify = useVerifySignup()
  const started = useRef(false)

  useEffect(() => {
    if (!token || started.current) return
    started.current = true
    verify.mutate(token)
  }, [token, verify])

  const progress = useSignupProgress(token, verify.isSuccess)
  const state = progress.data ?? verify.data

  if (!token || verify.isError) {
    return (
      <Centered>
        <AlertCircle className="mx-auto mb-4 size-10 text-red-500" aria-hidden />
        <h1 className="text-xl font-semibold text-slate-900">We couldn't use this link</h1>
        <div className="mt-4 text-left">
          <ErrorAlert error={verify.error ?? new Error('The link is incomplete. Open it straight from the email.')} />
        </div>
        <Link to="/signup" className="mt-6 inline-block font-medium text-brand-600 hover:text-brand-700">
          Sign up again
        </Link>
      </Centered>
    )
  }

  if (state?.status === 'ready' && state.login_url) {
    const signIn = `${state.login_url}${state.email ? `?email=${encodeURIComponent(state.email)}` : ''}`
    return (
      <Centered>
        <CheckCircle2 className="mx-auto mb-4 size-12 text-emerald-500" aria-hidden />
        <h1 className="text-2xl font-semibold text-slate-900">{state.hospital_name} is ready</h1>
        <p className="mt-3 text-slate-600">
          Your hospital's address is{' '}
          <span className="font-medium text-slate-900">{state.login_url.replace(/\/login$/, '')}</span>. Bookmark it:
          this is where you and your staff will sign in.
        </p>
        <a
          href={signIn}
          className="mt-8 inline-block rounded-lg bg-brand-500 px-5 py-3 font-medium text-white shadow-sm hover:bg-brand-600"
        >
          Sign in to {state.hospital_name}
        </a>
        <p className="mt-4 text-sm text-slate-500">We've also emailed you the address.</p>
      </Centered>
    )
  }

  if (state?.status === 'failed') {
    return (
      <Centered>
        <AlertCircle className="mx-auto mb-4 size-10 text-red-500" aria-hidden />
        <h1 className="text-xl font-semibold text-slate-900">We couldn't set up your hospital</h1>
        <p className="mt-3 text-slate-600">{state.error}</p>
        <Link to="/signup" className="mt-6 inline-block font-medium text-brand-600 hover:text-brand-700">
          Sign up again
        </Link>
      </Centered>
    )
  }

  return (
    <Centered>
      <Loader2 className="mx-auto mb-4 size-10 animate-spin text-brand-500" aria-hidden />
      <h1 className="text-xl font-semibold text-slate-900">
        {state ? `Setting up ${state.hospital_name}…` : 'Confirming your email…'}
      </h1>
      <p className="mt-3 text-slate-600" role="status">
        {state?.stalled
          ? "This is taking longer than usual. You can close this page: we'll email you as soon as it's ready."
          : 'Your email is confirmed. Creating your hospital usually takes about a minute; please keep this page open.'}
      </p>
    </Centered>
  )
}
