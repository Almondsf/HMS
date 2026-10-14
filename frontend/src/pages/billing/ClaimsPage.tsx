import { FileText, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { useClaimAction, useClaims, type Claim, type ClaimStatus } from '@/api/billing'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, EmptyState, ErrorAlert, Input, PageHeader, Spinner, cx } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { formatMoney, useHospital } from '@/lib/hospital'

export const CLAIM_STATUS: Record<ClaimStatus, { label: string; tone: 'gray' | 'brand' | 'green' | 'red' | 'amber' }> = {
  draft: { label: 'Draft', tone: 'gray' },
  submitted: { label: 'Submitted', tone: 'brand' },
  approved: { label: 'Approved', tone: 'amber' },
  rejected: { label: 'Rejected', tone: 'red' },
  paid: { label: 'Paid', tone: 'green' },
}

const TABS: ClaimStatus[] = ['draft', 'submitted', 'approved', 'paid', 'rejected']

function RespondModal({ claim, onClose }: { claim: Claim; onClose: () => void }) {
  const action = useClaimAction()
  const [decision, setDecision] = useState<'approve' | 'reject'>('approve')
  const [amount, setAmount] = useState(claim.claimed_amount)
  const [reason, setReason] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const body = decision === 'approve' ? { approved_amount: amount } : { rejection_reason: reason }
    action.mutate({ id: claim.id, action: 'respond', body }, { onSuccess: onClose })
  }

  return (
    <Modal open title={`Insurer's decision · ${claim.number}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={action.error} />
        <div className="flex gap-4 text-sm">
          {(['approve', 'reject'] as const).map((option) => (
            <label key={option} className="flex items-center gap-2">
              <input type="radio" className="accent-brand-500" checked={decision === option} onChange={() => setDecision(option)} />
              {option === 'approve' ? 'Approved' : 'Rejected'}
            </label>
          ))}
        </div>
        {decision === 'approve' ? (
          <Input label="Approved amount" type="number" min={0.01} max={claim.claimed_amount} step="0.01" required value={amount} onChange={(e) => setAmount(e.target.value)} hint="Less than claimed for a partial approval; the rest returns to the patient." />
        ) : (
          <Input label="Rejection reason" required value={reason} onChange={(e) => setReason(e.target.value)} />
        )}
        <div className="flex justify-end">
          <Button type="submit" loading={action.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function PayModal({ claim, onClose }: { claim: Claim; onClose: () => void }) {
  const action = useClaimAction()
  const [amount, setAmount] = useState(claim.approved_amount ?? claim.claimed_amount)
  const [reference, setReference] = useState('')
  return (
    <Modal open title={`Insurer payment · ${claim.number}`} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          action.mutate({ id: claim.id, action: 'pay', body: { amount, reference } }, { onSuccess: onClose })
        }}
        className="space-y-4"
      >
        <ErrorAlert error={action.error} />
        <Input label="Amount received" type="number" min={0.01} step="0.01" required value={amount} onChange={(e) => setAmount(e.target.value)} hint="Any shortfall returns to the patient's balance." />
        <Input label="Remittance reference" value={reference} onChange={(e) => setReference(e.target.value)} />
        <div className="flex justify-end">
          <Button type="submit" loading={action.isPending}>
            Record payment
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function ClaimCard({ claim }: { claim: Claim }) {
  const action = useClaimAction()
  const { data: hospital } = useHospital()
  const [dialog, setDialog] = useState<'respond' | 'pay' | null>(null)
  const money = (value: string | null) => (value ? formatMoney(value, hospital?.currency) : '—')

  return (
    <Card className="flex flex-wrap items-center gap-4 p-5">
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-900">
          {claim.patient_name} <span className="font-normal text-slate-500">· {claim.provider_name}</span>
        </p>
        <p className="text-xs text-slate-500">
          {claim.number} · invoice{' '}
          <Link to={`/billing/invoices/${claim.invoice}`} className="text-brand-700 hover:underline">
            {claim.invoice_number}
          </Link>{' '}
          · {formatDate(claim.created_at)}
          {claim.rejection_reason ? ` · ${claim.rejection_reason}` : ''}
        </p>
        <p className="mt-1 text-sm text-slate-700">
          Claimed {money(claim.claimed_amount)}
          {claim.approved_amount && ` · approved ${money(claim.approved_amount)}`}
          {Number(claim.paid_amount) > 0 && ` · paid ${money(claim.paid_amount)}`}
        </p>
      </div>
      <Badge tone={CLAIM_STATUS[claim.status].tone}>{CLAIM_STATUS[claim.status].label}</Badge>
      <div className="flex gap-2">
        <Link to={`/insurance/claims/${claim.id}/document`} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm text-brand-600 hover:bg-brand-50">
          <FileText className="size-4" aria-hidden /> Document
        </Link>
        {claim.status === 'draft' && (
          <Button size="sm" loading={action.isPending} onClick={() => action.mutate({ id: claim.id, action: 'submit' })}>
            Mark submitted
          </Button>
        )}
        {claim.status === 'submitted' && (
          <Button size="sm" variant="secondary" onClick={() => setDialog('respond')}>
            Record decision
          </Button>
        )}
        {(claim.status === 'submitted' || claim.status === 'approved') && (
          <Button size="sm" onClick={() => setDialog('pay')}>
            Payment received
          </Button>
        )}
      </div>
      {action.error && <p className="w-full text-sm text-red-600">{action.error.message}</p>}
      {dialog === 'respond' && <RespondModal claim={claim} onClose={() => setDialog(null)} />}
      {dialog === 'pay' && <PayModal claim={claim} onClose={() => setDialog(null)} />}
    </Card>
  )
}

export function ClaimsPage() {
  const [tab, setTab] = useState<ClaimStatus>('draft')
  const { data: claims, isLoading, error } = useClaims({ status: tab })

  return (
    <>
      <PageHeader title="Insurance claims" description="Create claims from issued invoices, then track them to payment." />
      <div role="tablist" className="mb-4 inline-flex flex-wrap rounded-lg border border-slate-200 bg-white p-1">
        {TABS.map((status) => (
          <button
            key={status}
            role="tab"
            aria-selected={tab === status}
            onClick={() => setTab(status)}
            className={cx('rounded-md px-3 py-1.5 text-sm font-medium', tab === status ? 'bg-brand-500 text-white' : 'text-slate-600 hover:bg-slate-50')}
          >
            {CLAIM_STATUS[status].label}
          </button>
        ))}
      </div>
      <ErrorAlert error={error} />
      {isLoading ? (
        <Spinner />
      ) : !claims?.length ? (
        <Card>
          <EmptyState icon={<ShieldCheck className="size-6" />} title="No claims here" />
        </Card>
      ) : (
        <div className="space-y-4">
          {claims.map((claim) => (
            <ClaimCard key={claim.id} claim={claim} />
          ))}
        </div>
      )}
    </>
  )
}
