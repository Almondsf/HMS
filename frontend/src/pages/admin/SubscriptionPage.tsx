import { Check, CreditCard, Receipt } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'

import {
  useCancelAutoRenew,
  useCheckout,
  useConfirmPayment,
  useSubscription,
  type Interval,
  type PlanPrice,
  type SubscriptionSummary,
} from '@/api/subscription'
import { Badge, Button, Card, cx, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { formatDate, titleCase } from '@/lib/format'
import { formatMoney, type Hospital } from '@/lib/hospital'

const PLAN_MODULES: Record<Hospital['plan'], string[]> = {
  basic: ['Patients, queue & appointments', 'Consultations & nursing', 'Pharmacy', 'Billing & receipts'],
  pro: ['Everything in Basic', 'Laboratory', 'Insurance (HMO) claims'],
  enterprise: ['Everything in Pro', 'Priority support', 'Custom onboarding'],
}

const STATUS_TONES = {
  trialing: 'brand',
  active: 'green',
  past_due: 'amber',
  cancelled: 'gray',
} as const

const STATUS_LABELS = {
  trialing: 'Free trial',
  active: 'Active',
  past_due: 'Payment overdue',
  cancelled: 'Not renewing',
} as const

function StatusCard({ summary }: { summary: SubscriptionSummary }) {
  const cancel = useCancelAutoRenew()
  const ending = summary.status === 'trialing' ? 'Trial ends' : summary.cancel_at_period_end ? 'Access ends' : 'Renews'

  return (
    <Card className="mb-6 space-y-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-lg font-semibold text-slate-900">{titleCase(summary.plan)} plan</span>
        <Badge tone={STATUS_TONES[summary.status]}>{STATUS_LABELS[summary.status]}</Badge>
        {summary.access === 'read_only' && <Badge tone="red">Read-only</Badge>}
      </div>
      <dl className="grid gap-4 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">{summary.access === 'full' ? ending : 'Paid until'}</dt>
          <dd className="font-medium text-slate-900">{formatDate(summary.current_period_end)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Days left</dt>
          <dd className="font-medium text-slate-900">{summary.days_left}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Billing</dt>
          <dd className="font-medium text-slate-900">
            {titleCase(summary.interval)}
            {summary.auto_renews ? ', renews automatically' : ''}
          </dd>
        </div>
      </dl>
      {summary.access === 'warning' && (
        <p className="text-sm text-amber-800">
          Payment is overdue. Everything keeps working until {formatDate(summary.grace_ends_at)}; after that records
          become read-only until you pay.
        </p>
      )}
      {summary.access === 'read_only' && (
        <p className="text-sm text-red-700">
          Records can be viewed but nothing new can be saved. Pay below to restore full access immediately.
        </p>
      )}
      {summary.auto_renews && (
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
          <ErrorAlert error={cancel.error} />
          <Button
            variant="secondary"
            size="sm"
            loading={cancel.isPending}
            onClick={() => {
              if (window.confirm('Stop automatic renewal? Access continues until the paid period ends.'))
                cancel.mutate()
            }}
          >
            Stop automatic renewal
          </Button>
        </div>
      )}
    </Card>
  )
}

function PlanCard({
  plan,
  price,
  current,
  online,
}: {
  plan: Hospital['plan']
  price?: PlanPrice
  current: boolean
  online: boolean
}) {
  const checkout = useCheckout()
  return (
    <Card className={cx('flex flex-col gap-4 p-5', current && 'ring-2 ring-brand-500')}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">{titleCase(plan)}</h3>
        {current && <Badge tone="brand">Current plan</Badge>}
      </div>
      <p>
        <span className="text-2xl font-semibold text-slate-900">
          {price ? formatMoney(price.amount, price.currency) : '—'}
        </span>
        {price && <span className="text-sm text-slate-500"> / {price.interval === 'yearly' ? 'year' : 'month'}</span>}
      </p>
      <ul className="flex-1 space-y-2 text-sm text-slate-600">
        {PLAN_MODULES[plan].map((item) => (
          <li key={item} className="flex gap-2">
            <Check className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden />
            {item}
          </li>
        ))}
      </ul>
      <ErrorAlert error={checkout.error} />
      {online && price && (
        <Button
          variant={current ? 'primary' : 'secondary'}
          icon={<CreditCard className="size-4" />}
          loading={checkout.isPending || checkout.isSuccess}
          onClick={() =>
            checkout.mutate(
              { plan, interval: price.interval },
              // Paystack's page takes the payment, then sends the payer back here
              {
                onSuccess: ({ authorization_url }) => window.location.assign(authorization_url),
              },
            )
          }
        >
          {current ? 'Pay & renew' : `Switch to ${titleCase(plan)}`}
        </Button>
      )}
    </Card>
  )
}

/** Paystack sends the payer back with ?reference=...: confirm it once (the server verifies with Paystack). */
function useReturnFromPaystack() {
  const [params, setParams] = useSearchParams()
  const confirm = useConfirmPayment()
  const reference = params.get('reference') ?? params.get('trxref')
  const started = useRef(false)

  useEffect(() => {
    if (!reference || started.current) return
    started.current = true
    confirm.mutate(reference, {
      onSettled: () => setParams({}, { replace: true }),
    })
  }, [reference, confirm, setParams])

  return confirm
}

export function SubscriptionPage() {
  const { data: summary, isLoading, error } = useSubscription()
  const confirm = useReturnFromPaystack()
  const [period, setPeriod] = useState<Interval>('monthly')

  if (isLoading || confirm.isPending)
    return <Spinner label={confirm.isPending ? 'Confirming your payment' : 'Loading'} />
  if (!summary) return <ErrorAlert error={error} />

  const prices = summary.prices ?? []
  const payments = summary.payments ?? []

  return (
    <>
      <PageHeader title="Subscription" description="Your plan, renewals and payments for this hospital" />
      {confirm.isSuccess && (
        <div
          role="status"
          className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"
        >
          Payment received, thank you. Your subscription has been updated.
        </div>
      )}
      <div className="mb-6">
        <ErrorAlert error={confirm.error} />
      </div>
      <StatusCard summary={summary} />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-medium text-slate-900">Plans</h2>
        <div
          role="group"
          aria-label="Billing period"
          className="inline-flex rounded-lg border border-slate-200 bg-white p-1"
        >
          {(['monthly', 'yearly'] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={period === option}
              onClick={() => setPeriod(option)}
              className={cx(
                'rounded-md px-3 py-1.5 text-sm font-medium',
                period === option ? 'bg-brand-500 text-white' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              {option === 'monthly' ? 'Monthly' : 'Yearly (2 months free)'}
            </button>
          ))}
        </div>
      </div>
      <div className="mb-8 grid gap-4 md:grid-cols-3">
        {(['basic', 'pro', 'enterprise'] as const).map((plan) => (
          <PlanCard
            key={plan}
            plan={plan}
            price={prices.find((price) => price.plan === plan && price.interval === period)}
            current={summary.plan === plan && summary.status !== 'trialing'}
            online={summary.online_payments}
          />
        ))}
      </div>
      {!summary.online_payments && (
        <Card className="mb-8 p-5 text-sm text-slate-600">
          Online payment isn't set up yet. To pay by bank transfer, contact the platform team; your subscription is
          updated as soon as the transfer is recorded.
        </Card>
      )}

      <h2 className="mb-4 font-medium text-slate-900">Payment history</h2>
      <Card>
        {payments.length === 0 ? (
          <EmptyState icon={<Receipt className="size-5" />} title="No payments yet" />
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
                {payments.map((payment) => (
                  <tr key={payment.reference}>
                    <td className="px-4 py-3">{formatDate(payment.paid_at)}</td>
                    <td className="px-4 py-3">
                      {titleCase(payment.plan)} ({payment.interval})
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatMoney(payment.amount, payment.currency)}
                    </td>
                    <td className="px-4 py-3">{formatDate(payment.period_end)}</td>
                    <td className="px-4 py-3">{payment.source === 'paystack' ? 'Paystack' : 'Bank transfer'}</td>
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
