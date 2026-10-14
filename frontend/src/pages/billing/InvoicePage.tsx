import { Ban, CreditCard, FileCheck2, Percent, Plus, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import {
  PAYMENT_METHODS,
  useClaims,
  useCoverages,
  useCreateClaim,
  useInvoice,
  useInvoiceAction,
  useServiceItems,
  useTakePayment,
  useVoidPayment,
  type Invoice,
  type InvoiceLine,
  type PaymentMethod,
} from '@/api/billing'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useCurrentUser } from '@/lib/auth'
import { formatDateTime, titleCase } from '@/lib/format'
import { formatMoney, useHospital } from '@/lib/hospital'
import { INVOICE_STATUS } from '@/pages/billing/BillingPage'
import { CLAIM_STATUS } from '@/pages/billing/ClaimsPage'

function PriceLine({ invoiceId, line }: { invoiceId: number; line: InvoiceLine }) {
  const action = useInvoiceAction(invoiceId)
  const [price, setPrice] = useState('')
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        action.mutate({ path: `lines/${line.id}/price/`, body: { unit_price: price } })
      }}
      className="flex items-center gap-2"
    >
      <input
        type="number"
        min={0}
        step="0.01"
        required
        placeholder="Price"
        aria-label={`Price for ${line.description}`}
        value={price}
        onChange={(event) => setPrice(event.target.value)}
        className="w-28 rounded-md border border-red-300 px-2 py-1 text-sm"
      />
      <Button type="submit" size="sm" loading={action.isPending}>
        Set
      </Button>
    </form>
  )
}

function AddLineModal({ invoiceId, onClose }: { invoiceId: number; onClose: () => void }) {
  const action = useInvoiceAction(invoiceId)
  const { data: items } = useServiceItems()
  const [serviceItem, setServiceItem] = useState('')
  const [description, setDescription] = useState('')
  const [price, setPrice] = useState('')
  const [quantity, setQuantity] = useState(1)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const body = serviceItem
      ? { service_item: Number(serviceItem), quantity }
      : { description, unit_price: price, quantity }
    action.mutate({ path: 'lines/', body }, { onSuccess: onClose })
  }

  return (
    <Modal open title="Add charge" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={action.error} />
        <Select label="Service" value={serviceItem} onChange={(event) => setServiceItem(event.target.value)}>
          <option value="">Other (describe below)</option>
          {items
            ?.filter((item) => item.is_active)
            .map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {formatMoney(item.price)}
              </option>
            ))}
        </Select>
        {!serviceItem && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Description" required value={description} onChange={(e) => setDescription(e.target.value)} />
            <Input label="Unit price" type="number" min={0} step="0.01" required value={price} onChange={(e) => setPrice(e.target.value)} />
          </div>
        )}
        <Input label="Quantity" type="number" min={1} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} />
        <div className="flex justify-end">
          <Button type="submit" loading={action.isPending}>
            Add
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function PaymentModal({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const pay = useTakePayment(invoice.id)
  const { data: hospital } = useHospital()
  const [amount, setAmount] = useState(invoice.patient_due)
  const [method, setMethod] = useState<PaymentMethod>('cash')
  const [reference, setReference] = useState('')
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const errors = pay.error instanceof ApiError ? pay.error.fieldErrors : {}

  if (receiptId) {
    return (
      <Modal open title="Payment recorded" onClose={onClose}>
        <div className="space-y-4">
          <p className="text-sm text-slate-600">The payment is saved.</p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
            <Link to={`/billing/payments/${receiptId}/receipt`} className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600">
              Print receipt
            </Link>
          </div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal open title="Take payment" onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          pay.mutate({ amount, method, reference }, { onSuccess: (payment) => setReceiptId(payment.id) })
        }}
        className="space-y-4"
      >
        <ErrorAlert error={Object.keys(errors).length ? null : pay.error} />
        <p className="text-sm text-slate-600">
          Patient owes <strong>{formatMoney(invoice.patient_due, hospital?.currency)}</strong>
          {Number(invoice.pending_insurance) > 0 &&
            ` (insurance expected to cover ${formatMoney(invoice.pending_insurance, hospital?.currency)})`}
        </p>
        <Input label="Amount" type="number" min={0.01} step="0.01" max={invoice.patient_due} required value={amount} onChange={(e) => setAmount(e.target.value)} error={errors.amount} />
        <Select label="Method" value={method} onChange={(e) => setMethod(e.target.value as PaymentMethod)}>
          {PAYMENT_METHODS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        {method !== 'cash' && (
          <Input label="Reference" value={reference} onChange={(e) => setReference(e.target.value)} hint="POS slip or transfer reference" />
        )}
        <div className="flex justify-end">
          <Button type="submit" loading={pay.isPending}>
            Record payment
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function DiscountModal({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const action = useInvoiceAction(invoice.id)
  const [amount, setAmount] = useState(invoice.discount)
  const [reason, setReason] = useState(invoice.discount_reason)
  return (
    <Modal open title="Discount" onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          action.mutate({ path: 'discount/', body: { amount, reason } }, { onSuccess: onClose })
        }}
        className="space-y-4"
      >
        <ErrorAlert error={action.error} />
        <Input label="Amount" type="number" min={0} step="0.01" required value={amount} onChange={(e) => setAmount(e.target.value)} />
        <Input label="Reason" required value={reason} onChange={(e) => setReason(e.target.value)} />
        <div className="flex justify-end">
          <Button type="submit" loading={action.isPending}>
            Apply
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function InsurancePanel({ invoice }: { invoice: Invoice }) {
  const { data: claims } = useClaims({ invoice: invoice.id })
  const { data: coverages } = useCoverages(invoice.patient, true)
  const create = useCreateClaim(invoice.id)
  const [coverage, setCoverage] = useState('')
  const [authorization, setAuthorization] = useState('')
  const openClaim = claims?.some((claim) => ['draft', 'submitted', 'approved'].includes(claim.status))
  const usable = coverages?.filter((cover) => cover.is_active) ?? []

  return (
    <Card className="space-y-3 p-5">
      <h2 className="flex items-center gap-2 font-medium text-slate-900">
        <ShieldCheck className="size-4 text-brand-600" aria-hidden /> Insurance
      </h2>
      {claims?.map((claim) => (
        <div key={claim.id} className="flex items-center justify-between gap-2 text-sm">
          <Link to="/insurance/claims" className="font-mono text-xs text-brand-700 hover:underline">
            {claim.number}
          </Link>
          <span className="text-slate-600">{claim.provider_name}</span>
          <Badge tone={CLAIM_STATUS[claim.status].tone}>{CLAIM_STATUS[claim.status].label}</Badge>
        </div>
      ))}
      {invoice.status === 'issued' && !openClaim && (
        usable.length === 0 ? (
          <p className="text-sm text-slate-500">This patient has no insurance cover on record.</p>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault()
              create.mutate({ coverage: Number(coverage), authorization_code: authorization })
            }}
            className="space-y-3"
          >
            <ErrorAlert error={create.error} />
            <Select label="Claim from" required value={coverage} onChange={(e) => setCoverage(e.target.value)}>
              <option value="">Choose cover</option>
              {usable.map((cover) => (
                <option key={cover.id} value={cover.id}>
                  {cover.provider_name} · {cover.member_number} ({Number(cover.effective_percent)}%)
                </option>
              ))}
            </Select>
            <Input label="Authorisation code" value={authorization} onChange={(e) => setAuthorization(e.target.value)} hint="If the insurer requires one" />
            <Button type="submit" size="sm" loading={create.isPending} disabled={!coverage}>
              Create claim
            </Button>
          </form>
        )
      )}
    </Card>
  )
}

export function InvoicePage() {
  const { id } = useParams()
  const invoiceId = Number(id)
  const user = useCurrentUser()
  const { data: hospital } = useHospital()
  const { data: invoice, isLoading, error } = useInvoice(invoiceId)
  const action = useInvoiceAction(invoiceId)
  const voidPayment = useVoidPayment(invoiceId)
  const [dialog, setDialog] = useState<'line' | 'pay' | 'discount' | null>(null)

  if (isLoading) return <Spinner />
  if (!invoice) return <ErrorAlert error={error ?? new Error('Invoice not found.')} />

  const money = (value: string) => formatMoney(value, hospital?.currency)
  const isAdmin = user.user_type === 'admin'
  const canManage = isAdmin || user.user_type === 'cashier'
  const draft = invoice.status === 'draft'
  const payable = (draft || invoice.status === 'issued') && Number(invoice.patient_due) > 0
  const status = INVOICE_STATUS[invoice.status]
  const insurance = hospital?.features.includes('insurance') ?? false

  function voidWithReason(path: string, what: string) {
    const reason = window.prompt(`Why void ${what}?`)
    if (reason) action.mutate({ path, body: { reason } })
  }

  return (
    <>
      <PageHeader
        title={`Invoice ${invoice.number}`}
        description={`${invoice.patient_name} · ${invoice.patient_mrn} · ${formatDateTime(invoice.created_at)}`}
        actions={
          <>
            <Badge tone={status.tone}>{status.label}</Badge>
            {canManage && draft && (
              <Button variant="secondary" icon={<Plus className="size-4" />} onClick={() => setDialog('line')}>
                Add charge
              </Button>
            )}
            {isAdmin && (draft || invoice.status === 'issued') && (
              <Button variant="secondary" icon={<Percent className="size-4" />} onClick={() => setDialog('discount')}>
                Discount
              </Button>
            )}
            {canManage && draft && (
              <Button variant="secondary" icon={<FileCheck2 className="size-4" />} loading={action.isPending} onClick={() => action.mutate({ path: 'issue/' })}>
                Issue
              </Button>
            )}
            {payable && (
              <Button icon={<CreditCard className="size-4" />} onClick={() => setDialog('pay')}>
                Take payment
              </Button>
            )}
          </>
        }
      />
      <ErrorAlert error={action.error ?? voidPayment.error} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Item</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Price</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {invoice.lines.map((line) => (
                <tr key={line.id} className={line.voided ? 'text-slate-400 line-through' : ''}>
                  <td className="px-4 py-3">
                    <p className="text-slate-900">{line.description}</p>
                    <p className="text-xs text-slate-500">{titleCase(line.category)}</p>
                    {line.voided && <p className="text-xs no-underline">Voided: {line.void_reason}</p>}
                  </td>
                  <td className="px-4 py-3 text-right">{line.quantity}</td>
                  <td className="px-4 py-3 text-right">
                    {line.needs_price && !line.voided && draft && canManage ? (
                      <PriceLine invoiceId={invoice.id} line={line} />
                    ) : (
                      money(line.unit_price)
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-medium">{money(line.amount)}</td>
                  <td className="px-4 py-3 text-right">
                    {draft && canManage && !line.voided && (
                      <button
                        type="button"
                        onClick={() => voidWithReason(`lines/${line.id}/void/`, `“${line.description}”`)}
                        className="rounded p-1 text-slate-400 hover:text-red-600"
                        aria-label={`Void ${line.description}`}
                      >
                        <Ban className="size-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <div className="space-y-6">
          <Card className="space-y-2 p-5 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">Subtotal</span>
              <span>{money(invoice.subtotal)}</span>
            </div>
            {Number(invoice.discount) > 0 && (
              <div className="flex justify-between">
                <span className="text-slate-600" title={invoice.discount_reason}>
                  Discount
                </span>
                <span>−{money(invoice.discount)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-slate-200 pt-2 font-medium">
              <span>Total</span>
              <span>{money(invoice.total)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Paid</span>
              <span>{money(invoice.amount_paid)}</span>
            </div>
            {Number(invoice.pending_insurance) > 0 && (
              <div className="flex justify-between">
                <span className="text-slate-600">Insurance pending</span>
                <span>{money(invoice.pending_insurance)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold text-brand-700">
              <span>Patient owes</span>
              <span>{money(invoice.patient_due)}</span>
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 font-medium text-slate-900">Payments</h2>
            {invoice.payments.length === 0 ? (
              <p className="text-sm text-slate-500">None yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {invoice.payments.map((payment) => (
                  <li key={payment.id} className="flex flex-wrap items-center justify-between gap-2">
                    <Link to={`/billing/payments/${payment.id}/receipt`} className={`font-mono text-xs hover:underline ${payment.voided ? 'text-slate-400 line-through' : 'text-brand-700'}`}>
                      {payment.receipt_number}
                    </Link>
                    <span className="text-slate-600">{titleCase(payment.method)}</span>
                    <span className="font-medium">{money(payment.amount)}</span>
                    {isAdmin && !payment.voided && (
                      <button
                        type="button"
                        className="text-xs text-red-600 hover:underline"
                        onClick={() => {
                          const reason = window.prompt('Why void this payment?')
                          if (reason) voidPayment.mutate({ id: payment.id, reason })
                        }}
                      >
                        Void
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {insurance && <InsurancePanel invoice={invoice} />}

          {isAdmin && (draft || invoice.status === 'issued') && Number(invoice.amount_paid) === 0 && (
            <Button variant="ghost" className="w-full text-red-600" onClick={() => voidWithReason('void/', 'this invoice')}>
              Void invoice
            </Button>
          )}
        </div>
      </div>

      {dialog === 'line' && <AddLineModal invoiceId={invoice.id} onClose={() => setDialog(null)} />}
      {dialog === 'pay' && <PaymentModal invoice={invoice} onClose={() => setDialog(null)} />}
      {dialog === 'discount' && <DiscountModal invoice={invoice} onClose={() => setDialog(null)} />}
    </>
  )
}
