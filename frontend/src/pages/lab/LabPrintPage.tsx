import { Printer } from 'lucide-react'
import { useParams } from 'react-router'

import { useLabOrder } from '@/api/labPharmacy'
import { Button, ErrorAlert, Spinner } from '@/components/ui'
import { formatDateTime, titleCase } from '@/lib/format'
import { useHospital } from '@/lib/hospital'

/** A printable lab report (the app's sidebar and header are hidden when printing). */
export function LabPrintPage() {
  const { id } = useParams()
  const { data: order, isLoading, error } = useLabOrder(Number(id))
  const { data: hospital } = useHospital()

  if (isLoading) return <Spinner />
  if (!order) return <ErrorAlert error={error ?? new Error('Order not found.')} />

  return (
    <div className="mx-auto max-w-3xl">
      <div className="no-print mb-4 flex justify-end">
        <Button icon={<Printer className="size-4" />} onClick={() => window.print()}>
          Print
        </Button>
      </div>
      <article className="rounded-xl border border-slate-200 bg-white p-8 print:border-0 print:p-0">
        <header className="mb-6 border-b-2 border-brand-500 pb-4">
          <h1 className="text-xl font-semibold text-slate-900">{hospital?.name}</h1>
          <p className="text-sm text-slate-500">{[hospital?.address, hospital?.phone].filter(Boolean).join(' · ')}</p>
          <p className="mt-3 text-sm font-semibold uppercase tracking-wide text-brand-700">Laboratory report</p>
        </header>
        <dl className="mb-6 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-slate-500">Patient</dt>
            <dd className="font-medium text-slate-900">{order.patient_name}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Order</dt>
            <dd className="font-medium text-slate-900">#{order.id}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Requested</dt>
            <dd className="text-slate-900">{formatDateTime(order.ordered_at)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Requested by</dt>
            <dd className="text-slate-900">{order.ordered_by_name ? `Dr ${order.ordered_by_name}` : 'Walk-in'}</dd>
          </div>
        </dl>
        <table className="w-full text-sm">
          <thead className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-2">Test</th>
              <th className="py-2">Result</th>
              <th className="py-2">Normal range</th>
              <th className="py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {order.results.map((result) => (
              <tr key={result.id}>
                <td className="py-2 text-slate-900">{result.test_name}</td>
                <td className="py-2 font-semibold text-slate-900">{result.result_value || '—'}</td>
                <td className="py-2 text-slate-600">{result.normal_range ?? '—'}</td>
                <td className="py-2 text-slate-600">{titleCase(result.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <footer className="mt-10 text-xs text-slate-500">
          {order.results
            .filter((result) => result.labtech_name)
            .map((result) => `${result.test_name}: ${result.labtech_name}`)
            .join(' · ')}
        </footer>
      </article>
    </div>
  )
}
