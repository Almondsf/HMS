import { ReceiptText } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { useInvoices, type InvoiceStatus } from '@/api/billing'
import { Badge, Card, EmptyState, ErrorAlert, PageHeader, Spinner, cx } from '@/components/ui'
import { formatDateTime } from '@/lib/format'
import { formatMoney, useHospital } from '@/lib/hospital'

export const INVOICE_STATUS: Record<InvoiceStatus, { label: string; tone: 'gray' | 'amber' | 'green' | 'red' }> = {
  draft: { label: 'Open', tone: 'gray' },
  issued: { label: 'Awaiting payment', tone: 'amber' },
  paid: { label: 'Paid', tone: 'green' },
  void: { label: 'Void', tone: 'red' },
}

const TABS: InvoiceStatus[] = ['draft', 'issued', 'paid', 'void']

export function BillingPage() {
  const [tab, setTab] = useState<InvoiceStatus>('draft')
  const { data: invoices, isLoading, error } = useInvoices({ status: tab })
  const { data: hospital } = useHospital()

  return (
    <>
      <PageHeader
        title="Billing"
        description="Charges collect on open invoices as patients are seen; issue them to take payment."
        actions={
          <Link to="/billing/summary" className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
            Daily summary
          </Link>
        }
      />
      <div role="tablist" className="mb-4 inline-flex flex-wrap rounded-lg border border-slate-200 bg-white p-1">
        {TABS.map((status) => (
          <button
            key={status}
            role="tab"
            aria-selected={tab === status}
            onClick={() => setTab(status)}
            className={cx(
              'rounded-md px-3 py-1.5 text-sm font-medium',
              tab === status ? 'bg-brand-500 text-white' : 'text-slate-600 hover:bg-slate-50',
            )}
          >
            {INVOICE_STATUS[status].label}
          </button>
        ))}
      </div>
      <ErrorAlert error={error} />
      <Card>
        {isLoading ? (
          <Spinner />
        ) : !invoices?.length ? (
          <EmptyState icon={<ReceiptText className="size-6" />} title="No invoices here" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Invoice</th>
                  <th className="px-4 py-3">Patient</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3 text-right">Patient owes</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-brand-50/50">
                    <td className="px-4 py-3">
                      <Link to={`/billing/invoices/${invoice.id}`} className="font-mono text-xs font-medium text-brand-700 hover:underline">
                        {invoice.number}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900">{invoice.patient_name}</p>
                      <p className="text-xs text-slate-500">{invoice.patient_mrn}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{formatDateTime(invoice.created_at)}</td>
                    <td className="px-4 py-3 text-right text-slate-900">{formatMoney(invoice.total, hospital?.currency)}</td>
                    <td className="px-4 py-3 text-right font-medium text-slate-900">
                      {formatMoney(invoice.patient_due, hospital?.currency)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {invoice.lines.some((line) => line.needs_price && !line.voided) && <Badge tone="red">Needs price</Badge>}
                    </td>
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
