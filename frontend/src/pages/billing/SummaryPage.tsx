import { useState } from 'react'

import { useDailySummary } from '@/api/billing'
import { Card, ErrorAlert, Input, PageHeader, Spinner } from '@/components/ui'
import { titleCase, todayIso } from '@/lib/format'
import { formatMoney, useHospital } from '@/lib/hospital'

function Breakdown({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <Card className="p-5">
      <h2 className="mb-3 font-medium text-slate-900">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">Nothing yet.</p>
      ) : (
        <dl className="space-y-2 text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4">
              <dt className="text-slate-600">{label}</dt>
              <dd className="font-medium text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  )
}

/** End-of-day reconciliation for the cash office. */
export function SummaryPage() {
  const [date, setDate] = useState(todayIso())
  const { data: summary, isLoading, error } = useDailySummary(date)
  const { data: hospital } = useHospital()
  const money = (value: string) => formatMoney(value, hospital?.currency)

  return (
    <>
      <PageHeader title="Daily summary" description="Money taken and charges raised on the day." />
      <div className="mb-6 sm:max-w-xs">
        <Input label="Day" type="date" value={date} max={todayIso()} onChange={(event) => setDate(event.target.value)} />
      </div>
      <ErrorAlert error={error} />
      {isLoading || !summary ? (
        <Spinner />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          <Card className="p-5">
            <p className="text-sm text-slate-500">Collected</p>
            <p className="mt-1 text-3xl font-semibold text-brand-700">{money(summary.payments.total)}</p>
            <p className="mt-1 text-sm text-slate-500">
              {summary.payments.count} payments · {summary.outstanding_invoices} invoices awaiting payment
            </p>
          </Card>
          <Breakdown
            title="By method"
            rows={Object.entries(summary.payments.by_method).map(([method, total]) => [titleCase(method), money(total)])}
          />
          <Breakdown
            title="By cashier"
            rows={Object.entries(summary.payments.by_cashier).map(([name, row]) => [`${name} (${row.count})`, money(row.total)])}
          />
          <Breakdown
            title={`Charges raised · ${money(summary.charges.total)}`}
            rows={Object.entries(summary.charges.by_category).map(([category, total]) => [titleCase(category), money(total)])}
          />
        </div>
      )}
    </>
  )
}
