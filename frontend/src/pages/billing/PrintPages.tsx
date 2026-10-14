import { Printer } from 'lucide-react'
import type { ReactNode } from 'react'
import { useParams } from 'react-router'

import { useClaimDocument, useReceipt } from '@/api/billing'
import { Button, ErrorAlert, Spinner } from '@/components/ui'
import { formatDate, formatDateTime, titleCase } from '@/lib/format'
import { formatMoney, useHospital } from '@/lib/hospital'

function PrintSheet({ title, children }: { title: string; children: ReactNode }) {
  const { data: hospital } = useHospital()
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
          <p className="text-sm text-slate-500">
            {[hospital?.address, hospital?.phone, hospital?.contact_email].filter(Boolean).join(' · ')}
          </p>
          <p className="mt-3 text-sm font-semibold uppercase tracking-wide text-brand-700">{title}</p>
        </header>
        {children}
      </article>
    </div>
  )
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{value || '—'}</dd>
    </div>
  )
}

export function ReceiptPage() {
  const { id } = useParams()
  const { data: receipt, isLoading, error } = useReceipt(Number(id))
  if (isLoading) return <Spinner />
  if (!receipt) return <ErrorAlert error={error ?? new Error('Receipt not found.')} />
  const money = (value: string) => formatMoney(value, receipt.currency)

  return (
    <PrintSheet title={receipt.voided ? 'Receipt — VOID' : 'Receipt'}>
      <dl className="mb-6 grid grid-cols-2 gap-3 text-sm">
        <Field label="Receipt" value={receipt.receipt_number} />
        <Field label="Date" value={formatDateTime(receipt.date)} />
        <Field label="Patient" value={`${receipt.patient.name} (${receipt.patient.mrn})`} />
        <Field label="Invoice" value={receipt.invoice_number} />
      </dl>
      <table className="mb-6 w-full text-sm">
        <thead className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="py-2">Item</th>
            <th className="py-2 text-right">Qty</th>
            <th className="py-2 text-right">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {receipt.lines.map((line) => (
            <tr key={line.id}>
              <td className="py-2">{line.description}</td>
              <td className="py-2 text-right">{line.quantity}</td>
              <td className="py-2 text-right">{money(line.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="ml-auto max-w-xs space-y-1 text-sm">
        <div className="flex justify-between">
          <dt>Invoice total</dt>
          <dd>{money(receipt.invoice_total)}</dd>
        </div>
        <div className="flex justify-between text-base font-semibold text-brand-700">
          <dt>Paid now ({receipt.method})</dt>
          <dd>{money(receipt.amount_paid_now)}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Balance</dt>
          <dd>{money(receipt.balance_after)}</dd>
        </div>
      </dl>
      <p className="mt-8 text-xs text-slate-500">
        {receipt.reference && `Ref ${receipt.reference} · `}Received by {receipt.received_by ?? '—'}
      </p>
    </PrintSheet>
  )
}

export function ClaimDocumentPage() {
  const { id } = useParams()
  const { data: document, isLoading, error } = useClaimDocument(Number(id))
  if (isLoading) return <Spinner />
  if (!document) return <ErrorAlert error={error ?? new Error('Claim not found.')} />
  const money = (value: string) => formatMoney(value)

  return (
    <PrintSheet title={`Insurance claim ${document.claim_number}`}>
      <dl className="mb-6 grid grid-cols-2 gap-3 text-sm">
        <Field label="Insurer" value={`${document.provider.name} (${document.provider.code})`} />
        <Field label="Member number" value={document.member.member_number} />
        <Field label="Member" value={document.member.name} />
        <Field label="Date of birth" value={formatDate(document.member.date_of_birth)} />
        <Field label="Hospital record (MRN)" value={document.member.mrn} />
        <Field label="Plan" value={document.member.plan} />
        <Field label="Date of service" value={formatDate(document.service_date)} />
        <Field label="Attending doctor" value={document.attending_doctor ? `Dr ${document.attending_doctor}` : null} />
        <Field label="Authorisation code" value={document.authorization_code} />
        <Field label="Invoice" value={document.invoice_number} />
      </dl>
      <h2 className="mb-2 text-sm font-semibold text-slate-900">Diagnoses</h2>
      <ul className="mb-6 space-y-1 text-sm">
        {document.diagnoses.length === 0 && <li className="text-slate-500">None recorded</li>}
        {document.diagnoses.map((diagnosis, index) => (
          <li key={index}>
            <span className="font-mono">{diagnosis.code ?? '—'}</span> {diagnosis.description}{' '}
            <span className="text-slate-500">
              ({titleCase(diagnosis.kind)}, {diagnosis.certainty})
            </span>
          </li>
        ))}
      </ul>
      <table className="mb-6 w-full text-sm">
        <thead className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="py-2">Service</th>
            <th className="py-2 text-right">Qty</th>
            <th className="py-2 text-right">Unit</th>
            <th className="py-2 text-right">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {document.lines.map((line, index) => (
            <tr key={index}>
              <td className="py-2">{line.description}</td>
              <td className="py-2 text-right">{line.quantity}</td>
              <td className="py-2 text-right">{money(line.unit_price)}</td>
              <td className="py-2 text-right">{money(line.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="ml-auto max-w-xs space-y-1 text-sm">
        <div className="flex justify-between">
          <dt>Invoice total</dt>
          <dd>{money(document.invoice_total)}</dd>
        </div>
        <div className="flex justify-between">
          <dt>Coverage</dt>
          <dd>{Number(document.coverage_percent)}%</dd>
        </div>
        <div className="flex justify-between text-base font-semibold text-brand-700">
          <dt>Amount claimed</dt>
          <dd>{money(document.claimed_amount)}</dd>
        </div>
      </dl>
    </PrintSheet>
  )
}
