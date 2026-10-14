import { FlaskConical, Plus, Printer } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { useLabCatalogue } from '@/api/clinical'
import type { Patient } from '@/api/frontDesk'
import {
  useLabOrders,
  usePlaceLabOrder,
  useUpdateResult,
  type OrderStatus,
  type TestOrder,
  type TestResult,
} from '@/api/labPharmacy'
import { PatientPicker } from '@/components/frontDesk'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, EmptyState, ErrorAlert, Input, PageHeader, Spinner, cx } from '@/components/ui'
import { formatDateTime, titleCase } from '@/lib/format'

const TABS: { status: OrderStatus; label: string }[] = [
  { status: 'pending', label: 'Pending' },
  { status: 'in_progress', label: 'In progress' },
  { status: 'completed', label: 'Completed' },
]

const RESULT_TONE: Record<TestResult['status'], 'gray' | 'brand' | 'amber' | 'green' | 'red'> = {
  pending: 'gray',
  collected: 'brand',
  in_progress: 'amber',
  completed: 'green',
  cancelled: 'red',
}

function ResultRow({ result }: { result: TestResult }) {
  const update = useUpdateResult()
  const [value, setValue] = useState('')
  const final = result.status === 'completed' || result.status === 'cancelled'

  function complete(event: FormEvent) {
    event.preventDefault()
    update.mutate({ id: result.id, status: 'completed', result_value: value.trim() })
  }

  return (
    <li className="space-y-2 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="min-w-0 flex-1 text-sm font-medium text-slate-900">
          {result.test_name}
          {result.normal_range && <span className="ml-2 text-xs font-normal text-slate-500">normal {result.normal_range}</span>}
        </p>
        <Badge tone={RESULT_TONE[result.status]}>{titleCase(result.status)}</Badge>
        {final ? (
          result.result_value && <span className="text-sm font-semibold text-slate-900">{result.result_value}</span>
        ) : (
          <div className="flex gap-2">
            {result.status === 'pending' && (
              <Button size="sm" variant="secondary" loading={update.isPending} onClick={() => update.mutate({ id: result.id, status: 'collected' })}>
                Sample collected
              </Button>
            )}
            {result.status === 'collected' && (
              <Button size="sm" variant="secondary" loading={update.isPending} onClick={() => update.mutate({ id: result.id, status: 'in_progress' })}>
                Start
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                const reason = window.prompt('Why is this test cancelled?')
                if (reason) update.mutate({ id: result.id, status: 'cancelled', notes: reason })
              }}
            >
              Cancel
            </Button>
          </div>
        )}
      </div>
      {!final && (
        <form onSubmit={complete} className="flex items-end gap-2">
          <div className="flex-1">
            <Input label="Result" value={value} onChange={(event) => setValue(event.target.value)} placeholder="e.g. Hb 12.4 g/dL" />
          </div>
          <Button type="submit" size="sm" disabled={!value.trim()} loading={update.isPending}>
            Complete
          </Button>
        </form>
      )}
      {update.error && <p className="text-sm text-red-600">{update.error.message}</p>}
    </li>
  )
}

function OrderCard({ order }: { order: TestOrder }) {
  return (
    <Card className="p-5">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{order.patient_name}</p>
          <p className="text-xs text-slate-500">
            #{order.id} · {formatDateTime(order.ordered_at)} ·{' '}
            {order.ordered_by_name ? `Dr ${order.ordered_by_name}` : 'walk-in'}
            {order.reason ? ` · ${order.reason}` : ''}
          </p>
        </div>
        <Link
          to={`/lab/orders/${order.id}/print`}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-brand-600 hover:bg-brand-50"
        >
          <Printer className="size-4" aria-hidden /> Print
        </Link>
      </div>
      <ul className="divide-y divide-slate-100">
        {order.results.map((result) => (
          <ResultRow key={result.id} result={result} />
        ))}
      </ul>
    </Card>
  )
}

function WalkInOrderModal({ onClose }: { onClose: () => void }) {
  const place = usePlaceLabOrder()
  const { data: tests } = useLabCatalogue(true)
  const [patient, setPatient] = useState<Patient | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [reason, setReason] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!patient) return
    place.mutate({ patient: patient.id, tests: selected, reason }, { onSuccess: onClose })
  }

  return (
    <Modal open title="Walk-in lab order" onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={place.error} />
        <PatientPicker value={patient} onChange={setPatient} />
        <fieldset className="grid gap-2 sm:grid-cols-2">
          <legend className="mb-2 text-sm font-medium text-slate-700">Tests</legend>
          {tests?.map((test) => (
            <label key={test.id} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <input
                type="checkbox"
                className="accent-brand-500"
                checked={selected.includes(test.id)}
                onChange={(event) =>
                  setSelected(event.target.checked ? [...selected, test.id] : selected.filter((id) => id !== test.id))
                }
              />
              {test.name}
            </label>
          ))}
        </fieldset>
        <Input label="Reason / referral" value={reason} onChange={(event) => setReason(event.target.value)} />
        <div className="flex justify-end">
          <Button type="submit" loading={place.isPending} disabled={!patient || selected.length === 0}>
            Place order
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function LabPage() {
  const [tab, setTab] = useState<OrderStatus>('pending')
  const [walkIn, setWalkIn] = useState(false)
  const { data: orders, isLoading, error } = useLabOrders(tab)

  return (
    <>
      <PageHeader
        title="Lab work"
        actions={
          <>
            <Link to="/lab/tests" className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
              Test list & prices
            </Link>
            <Button icon={<Plus className="size-4" />} onClick={() => setWalkIn(true)}>
              Walk-in order
            </Button>
          </>
        }
      />
      <div role="tablist" className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1">
        {TABS.map(({ status, label }) => (
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
            {label}
          </button>
        ))}
      </div>
      <ErrorAlert error={error} />
      {isLoading ? (
        <Spinner />
      ) : !orders?.length ? (
        <Card>
          <EmptyState icon={<FlaskConical className="size-6" />} title="Nothing here" />
        </Card>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))}
        </div>
      )}
      {walkIn && <WalkInOrderModal onClose={() => setWalkIn(false)} />}
    </>
  )
}
