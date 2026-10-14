import { useState } from 'react'

import {
  useReport,
  type ClinicalReport,
  type FinancialReport,
  type LabReport,
  type PharmacyReport,
  type ReportName,
} from '@/api/admin'
import { BarList, DailyColumns, StatTile, compact } from '@/components/charts'
import { Card, ErrorAlert, Input, PageHeader, Spinner, cx } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { titleCase, todayIso } from '@/lib/format'
import { formatMoney, useHospital } from '@/lib/hospital'
import type { Feature, Role } from '@/lib/roles'

const REPORTS: { name: ReportName; label: string; roles: Role[]; feature: Feature }[] = [
  { name: 'clinical', label: 'Clinical', roles: ['admin'], feature: 'clinical' },
  { name: 'financial', label: 'Financial', roles: ['admin', 'cashier'], feature: 'billing' },
  { name: 'pharmacy', label: 'Pharmacy', roles: ['admin', 'pharmacist'], feature: 'pharmacy' },
  { name: 'lab', label: 'Lab', roles: ['admin', 'lab_tech'], feature: 'lab' },
]

function minutes(value: number | null): string {
  return value === null ? '—' : value < 60 ? `${Math.round(value)} min` : `${(value / 60).toFixed(1)} h`
}

function Clinical({ period }: { period: { date_from: string; date_to: string } }) {
  const { data, isLoading, error } = useReport<ClinicalReport>('clinical', period)
  if (isLoading) return <Spinner />
  if (!data) return <ErrorAlert error={error} />
  const { visits } = data
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Visits" value={compact(visits.total)} detail={`${visits.by_status.completed ?? 0} completed`} />
        <StatTile label="New patients" value={compact(data.new_patients)} />
        <StatTile label="Average wait" value={minutes(visits.average_wait_minutes)} detail="Arrival to being seen" />
        <StatTile label="Average consultation" value={minutes(visits.average_consultation_minutes)} />
      </div>
      <DailyColumns title="Visits per day" points={visits.per_day.map((row) => ({ day: row.day, value: row.visits }))} />
      <div className="grid gap-6 lg:grid-cols-2">
        <BarList
          title="Top diagnoses"
          rows={data.top_diagnoses.map((row) => ({ key: row.code, label: `${row.code} · ${row.title}`, value: row.count }))}
        />
        <BarList
          title="Visits by doctor"
          rows={visits.per_doctor.map((row) => ({ key: String(row.doctor_id), label: `Dr ${row.doctor}`, value: row.visits }))}
        />
      </div>
    </div>
  )
}

function Financial({ period }: { period: { date_from: string; date_to: string } }) {
  const { data, isLoading, error } = useReport<FinancialReport>('financial', period)
  const { data: hospital } = useHospital()
  if (isLoading) return <Spinner />
  if (!data) return <ErrorAlert error={error} />
  const money = (value: number | string) => formatMoney(value, hospital?.currency)
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Collected" value={money(data.collected.total)} detail={`${money(data.collected.from_insurers)} from insurers`} />
        <StatTile label="Charged" value={money(data.charged.total)} />
        <StatTile label="Owed by patients" value={money(data.receivables.patients)} detail={`${data.receivables.invoices} unpaid invoices`} />
        <StatTile label="Owed by insurers" value={money(data.receivables.insurers)} />
      </div>
      <DailyColumns
        title="Collected per day"
        points={data.collected.per_day.map((row) => ({ day: row.day, value: Number(row.total) }))}
        format={money}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <BarList
          title="Charges by category"
          format={money}
          rows={Object.entries(data.charged.by_category).map(([category, total]) => ({ key: category, label: titleCase(category), value: Number(total) }))}
        />
        <BarList
          title="Unpaid balances by age (days since issue)"
          format={money}
          rows={Object.entries(data.receivables.aging_days).map(([bucket, total]) => ({ key: bucket, label: `${bucket} days`, value: Number(total) }))}
        />
        {data.insurance_outstanding && (
          <BarList
            title="Owed by each insurer"
            format={money}
            empty="No open claims."
            rows={Object.entries(data.insurance_outstanding).map(([name, row]) => ({ key: name, label: name, value: Number(row.total) }))}
          />
        )}
        <BarList
          title="Collected by method"
          format={money}
          rows={Object.entries(data.collected.by_method).map(([method, total]) => ({ key: method, label: titleCase(method), value: Number(total) }))}
        />
      </div>
    </div>
  )
}

function Pharmacy({ period }: { period: { date_from: string; date_to: string } }) {
  const { data, isLoading, error } = useReport<PharmacyReport>('pharmacy', period)
  const { data: hospital } = useHospital()
  if (isLoading) return <Spinner />
  if (!data) return <ErrorAlert error={error} />
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Stock value" value={formatMoney(data.stock_value, hospital?.currency)} />
        <StatTile label="Low on stock" value={data.low_stock.length} />
        <StatTile label="Drugs without a price" value={data.drugs_without_price} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <BarList
          title="Most dispensed (units)"
          rows={data.top_dispensed.map((row) => ({ key: String(row.drug_id), label: row.drug__name, value: row.quantity }))}
        />
        <Card className="p-5">
          <h3 className="mb-4 font-medium text-slate-900">Low stock</h3>
          {data.low_stock.length === 0 ? (
            <p className="text-sm text-slate-500">Everything is above its reorder level.</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.low_stock.map((drug) => (
                <li key={drug.id} className="flex justify-between py-2">
                  <span className="text-slate-700">{drug.name}</span>
                  <span className="tabular-nums text-slate-900">
                    {drug.quantity_in_stock} <span className="text-slate-500">(reorder at {drug.reorder_level})</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

function Lab({ period }: { period: { date_from: string; date_to: string } }) {
  const { data, isLoading, error } = useReport<LabReport>('lab', period)
  if (isLoading) return <Spinner />
  if (!data) return <ErrorAlert error={error} />
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Tests" value={compact(data.tests)} detail={`${data.by_status.completed ?? 0} completed`} />
        <StatTile
          label="Average turnaround"
          value={data.average_turnaround_hours === null ? '—' : `${data.average_turnaround_hours} h`}
          detail="Order to result"
        />
        <StatTile label="Pending now" value={data.pending_now} />
      </div>
      <BarList title="Tests by type" rows={data.by_test.map((row) => ({ key: row.test__name, label: row.test__name, value: row.count }))} />
    </div>
  )
}

function monthAgo(): string {
  const date = new Date()
  date.setDate(date.getDate() - 29)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

export function ReportsPage() {
  const user = useCurrentUser()
  const { data: hospital } = useHospital()
  const available = REPORTS.filter(
    (report) => report.roles.includes(user.user_type) && (hospital?.features ?? []).includes(report.feature),
  )
  const [active, setActive] = useState<ReportName | null>(null)
  const [period, setPeriod] = useState({ date_from: monthAgo(), date_to: todayIso() })
  const current = active ?? available[0]?.name

  return (
    <>
      <PageHeader title="Reports" description="Figures for the period, in hospital time." />
      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div role="tablist" className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
          {available.map((report) => (
            <button
              key={report.name}
              role="tab"
              aria-selected={current === report.name}
              onClick={() => setActive(report.name)}
              className={cx(
                'rounded-md px-3 py-1.5 text-sm font-medium',
                current === report.name ? 'bg-brand-500 text-white' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              {report.label}
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          <Input label="From" type="date" value={period.date_from} max={period.date_to} onChange={(e) => setPeriod({ ...period, date_from: e.target.value })} />
          <Input label="To" type="date" value={period.date_to} min={period.date_from} max={todayIso()} onChange={(e) => setPeriod({ ...period, date_to: e.target.value })} />
        </div>
      </div>
      {current === 'clinical' && <Clinical period={period} />}
      {current === 'financial' && <Financial period={period} />}
      {current === 'pharmacy' && <Pharmacy period={period} />}
      {current === 'lab' && <Lab period={period} />}
      {!current && <p className="text-sm text-slate-500">No reports are available for your role.</p>}
    </>
  )
}
