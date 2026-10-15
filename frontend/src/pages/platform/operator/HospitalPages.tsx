import { ArrowLeft, Building2, ExternalLink, Search } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import {
  hospitalState,
  useExtendAccess,
  useHospitals,
  usePlatformHospital,
  useRecordPayment,
  useUpdateHospital,
  type HospitalDetail,
  type HospitalState,
  type ManualPayment,
} from '@/api/platform'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorAlert,
  Input,
  PageHeader,
  Select,
  Spinner,
  Textarea,
} from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatDate, formatDateTime, titleCase } from '@/lib/format'
import type { Hospital } from '@/lib/hospital'

import { naira, STATE_LABELS, StateBadge } from './shared'

const PLAN_OPTIONS: Hospital['plan'][] = ['basic', 'pro', 'enterprise']

export function HospitalsPage() {
  const [search, setSearch] = useState('')
  const [state, setState] = useState<HospitalState | ''>('')
  const { data, isLoading, error } = useHospitals(search.trim())
  const hospitals = (data?.results ?? []).filter((hospital) => !state || hospitalState(hospital) === state)

  return (
    <>
      <PageHeader title="Hospitals" description={data ? `${data.count} in total` : undefined} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" aria-hidden />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, address or email"
            aria-label="Search hospitals"
            className="block w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>
        <select
          value={state}
          onChange={(event) => setState(event.target.value as HospitalState | '')}
          aria-label="Filter by state"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
        >
          <option value="">All states</option>
          {Object.entries(STATE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={error} />
      <Card>
        {isLoading ? (
          <Spinner />
        ) : hospitals.length === 0 ? (
          <EmptyState icon={<Building2 className="size-5" />} title="No hospitals match" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Hospital</th>
                  <th className="px-4 py-3 font-medium">Plan</th>
                  <th className="px-4 py-3 font-medium">State</th>
                  <th className="px-4 py-3 font-medium">Paid / trial until</th>
                  <th className="px-4 py-3 font-medium">Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {hospitals.map((hospital) => (
                  <tr key={hospital.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/operator/hospitals/${hospital.id}`}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        {hospital.name}
                      </Link>
                      <p className="text-xs text-slate-500">{hospital.domains[0]}</p>
                    </td>
                    <td className="px-4 py-3">{titleCase(hospital.plan)}</td>
                    <td className="px-4 py-3">
                      <StateBadge state={hospitalState(hospital)} />
                    </td>
                    <td className="px-4 py-3">{formatDate(hospital.subscription?.current_period_end)}</td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(hospital.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{children}</dd>
    </div>
  )
}

function ExtendForm({ hospital }: { hospital: HospitalDetail }) {
  const extend = useExtendAccess(hospital.id)
  const [days, setDays] = useState('14')
  const [reason, setReason] = useState('')
  const errors = extend.error instanceof ApiError ? extend.error.fieldErrors : {}

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    extend.mutate({ days: Number(days), reason }, { onSuccess: () => setReason('') })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <h3 className="font-medium text-slate-900">Give extra days</h3>
      <p className="text-sm text-slate-500">A longer trial, or time while a payment is sorted out.</p>
      <div className="grid gap-3 sm:grid-cols-[6rem_1fr]">
        <Input
          label="Days"
          type="number"
          min={1}
          max={90}
          required
          value={days}
          onChange={(event) => setDays(event.target.value)}
          error={errors.days}
        />
        <Input
          label="Reason"
          required
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          error={errors.reason}
          placeholder="e.g. Onboarding took longer"
        />
      </div>
      <ErrorAlert error={Object.keys(errors).length ? null : extend.error} />
      <div className="flex items-center gap-3">
        <Button type="submit" variant="secondary" loading={extend.isPending}>
          Extend access
        </Button>
        {extend.isSuccess && <span className="text-sm text-emerald-700">Extended</span>}
      </div>
    </form>
  )
}

function RecordPaymentForm({ hospital }: { hospital: HospitalDetail }) {
  const record = useRecordPayment(hospital.id)
  const empty: ManualPayment = {
    plan: hospital.plan,
    interval: hospital.subscription?.interval ?? 'monthly',
    amount: '',
    reference: '',
    note: '',
  }
  const [form, setForm] = useState<ManualPayment>(empty)
  const errors = record.error instanceof ApiError ? record.error.fieldErrors : {}
  const set = (field: keyof ManualPayment) => (event: { target: { value: string } }) =>
    setForm({ ...form, [field]: event.target.value })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    record.mutate(form, { onSuccess: () => setForm(empty) })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <h3 className="font-medium text-slate-900">Record a bank transfer</h3>
      <p className="text-sm text-slate-500">Extends the subscription by one period and switches to the paid plan.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <Select label="Plan" value={form.plan} onChange={set('plan')} error={errors.plan}>
          {PLAN_OPTIONS.map((plan) => (
            <option key={plan} value={plan}>
              {titleCase(plan)}
            </option>
          ))}
        </Select>
        <Select label="Period" value={form.interval} onChange={set('interval')} error={errors.interval}>
          <option value="monthly">Monthly</option>
          <option value="yearly">Yearly</option>
        </Select>
        <Input
          label="Amount (₦)"
          type="number"
          min={0}
          step="0.01"
          required
          value={form.amount}
          onChange={set('amount')}
          error={errors.amount}
        />
      </div>
      <Input
        label="Transfer reference"
        required
        value={form.reference}
        onChange={set('reference')}
        error={errors.reference}
        hint="From the bank alert; each reference can only be recorded once"
      />
      <Textarea label="Note (optional)" value={form.note} onChange={set('note')} />
      <ErrorAlert error={Object.keys(errors).length ? null : record.error} />
      <div className="flex items-center gap-3">
        <Button type="submit" loading={record.isPending}>
          Record payment
        </Button>
        {record.isSuccess && <span className="text-sm text-emerald-700">Recorded</span>}
      </div>
    </form>
  )
}

function PlanAndStatus({ hospital }: { hospital: HospitalDetail }) {
  const update = useUpdateHospital(hospital.id)
  const [plan, setPlan] = useState(hospital.plan)

  function toggleSuspended() {
    const message = hospital.is_active
      ? `Suspend ${hospital.name}? Nobody there can use the system until you reactivate it. No data is deleted.`
      : `Reactivate ${hospital.name}?`
    if (window.confirm(message)) update.mutate({ is_active: !hospital.is_active })
  }

  return (
    <div className="space-y-3">
      <h3 className="font-medium text-slate-900">Plan and access</h3>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-40">
          <Select label="Plan" value={plan} onChange={(event) => setPlan(event.target.value as Hospital['plan'])}>
            {PLAN_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {titleCase(option)}
              </option>
            ))}
          </Select>
        </div>
        <Button
          variant="secondary"
          disabled={plan === hospital.plan}
          loading={update.isPending && plan !== hospital.plan}
          onClick={() => update.mutate({ plan })}
        >
          Change plan
        </Button>
      </div>
      <p className="text-sm text-slate-500">
        Changing the plan switches modules on or off immediately; it doesn't charge anything.
      </p>
      <ErrorAlert error={update.error} />
      <div className="border-t border-slate-100 pt-3">
        <Button variant={hospital.is_active ? 'danger' : 'primary'} size="sm" onClick={toggleSuspended}>
          {hospital.is_active ? 'Suspend hospital' : 'Reactivate hospital'}
        </Button>
      </div>
    </div>
  )
}

export function HospitalDetailPage() {
  const id = Number(useParams().id)
  const { data: hospital, isLoading, error } = usePlatformHospital(id)
  if (isLoading) return <Spinner />
  if (!hospital) return <ErrorAlert error={error} />

  const subscription = hospital.subscription
  const address = hospital.domains[0]
  const { usage } = hospital

  return (
    <>
      <Link
        to="/operator/hospitals"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-brand-700"
      >
        <ArrowLeft className="size-4" aria-hidden /> All hospitals
      </Link>
      <PageHeader
        title={hospital.name}
        description={`Joined ${formatDate(hospital.created_at)}`}
        actions={
          address && (
            <a
              href={`${window.location.protocol}//${address}${window.location.port ? `:${window.location.port}` : ''}/login`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
            >
              {address} <ExternalLink className="size-3.5" aria-hidden />
            </a>
          )
        }
      />
      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card className="p-5">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="font-medium text-slate-900">Subscription</h3>
            <StateBadge state={hospitalState(hospital)} />
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Fact label="Plan">{titleCase(hospital.plan)}</Fact>
            <Fact label="Billing">{subscription ? titleCase(subscription.interval) : '—'}</Fact>
            <Fact label="Paid / trial until">{formatDate(subscription?.current_period_end)}</Fact>
            <Fact label="Days left">{subscription?.days_left ?? '—'}</Fact>
            <Fact label="Renews automatically">{subscription?.auto_renews ? 'Yes' : 'No'}</Fact>
          </dl>
        </Card>
        <Card className="p-5">
          <h3 className="mb-3 font-medium text-slate-900">Usage</h3>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Fact label="Active staff">{usage.active_staff}</Fact>
            <Fact label="Patients">{usage.patients}</Fact>
            <Fact label="Visits, last 30 days">{usage.visits_last_30_days}</Fact>
            <Fact label="Last sign-in">{usage.last_sign_in ? formatDateTime(usage.last_sign_in) : 'Never'}</Fact>
            <Fact label="Last activity">{usage.last_activity ? formatDateTime(usage.last_activity) : 'None'}</Fact>
          </dl>
        </Card>
        <Card className="p-5">
          <h3 className="mb-3 font-medium text-slate-900">Contact</h3>
          <dl className="space-y-3 text-sm">
            <Fact label="Email">{hospital.contact_email || '—'}</Fact>
            <Fact label="Phone">{hospital.phone || '—'}</Fact>
            <Fact label="Identifier">
              <span className="font-mono text-xs">{hospital.schema_name}</span>
            </Fact>
          </dl>
        </Card>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card className="space-y-6 p-5">
          <ExtendForm hospital={hospital} />
          <div className="border-t border-slate-100 pt-5">
            <PlanAndStatus key={hospital.plan} hospital={hospital} />
          </div>
        </Card>
        <Card className="p-5">
          <RecordPaymentForm key={hospital.payments.length} hospital={hospital} />
        </Card>
      </div>

      <h2 className="mb-3 font-medium text-slate-900">Payments</h2>
      <Card>
        {hospital.payments.length === 0 ? (
          <p className="px-5 py-4 text-sm text-slate-500">No payments yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Plan</th>
                  <th className="px-4 py-3 text-right font-medium">Amount</th>
                  <th className="px-4 py-3 font-medium">Paid until</th>
                  <th className="px-4 py-3 font-medium">Method</th>
                  <th className="px-4 py-3 font-medium">Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {hospital.payments.map((payment) => (
                  <tr key={payment.reference}>
                    <td className="px-4 py-3">{formatDate(payment.paid_at)}</td>
                    <td className="px-4 py-3">
                      {titleCase(payment.plan)} ({payment.interval})
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{naira(payment.amount)}</td>
                    <td className="px-4 py-3">{formatDate(payment.period_end)}</td>
                    <td className="px-4 py-3">
                      <Badge>{payment.source === 'paystack' ? 'Paystack' : 'Bank transfer'}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{payment.reference}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
