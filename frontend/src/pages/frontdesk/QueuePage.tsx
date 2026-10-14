import { ListOrdered } from 'lucide-react'
import { useState } from 'react'

import { useCancelVisit, useQueue, type QueueEntry, type TriageLevel } from '@/api/frontDesk'
import { DoctorSelect } from '@/components/frontDesk'
import { Badge, Button, Card, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { formatTime } from '@/lib/format'

export const TRIAGE: Record<TriageLevel, { label: string; tone: 'red' | 'amber' | 'brand' | 'gray' }> = {
  emergency: { label: 'Emergency', tone: 'red' },
  urgent: { label: 'Urgent', tone: 'amber' },
  standard: { label: 'Standard', tone: 'brand' },
  non_urgent: { label: 'Non-urgent', tone: 'gray' },
}

function waited(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

function QueueRow({ entry, canCancel }: { entry: QueueEntry; canCancel: boolean }) {
  const cancel = useCancelVisit()
  const triage = entry.triage_level ? TRIAGE[entry.triage_level] : null
  const inRoom = entry.status === 'in_progress'

  return (
    <li className={`flex flex-wrap items-center gap-4 px-4 py-3 ${inRoom ? 'bg-brand-50/60' : ''}`}>
      <div className="grid size-10 shrink-0 place-items-center rounded-full bg-white text-sm font-semibold text-brand-700 ring-1 ring-brand-200">
        {entry.position ?? '•'}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-900">{entry.patient.name}</p>
        <p className="text-xs text-slate-500">
          {entry.patient.mrn} · Dr {entry.doctor.name} · {entry.reason_for_visit}
          {entry.appointment_time ? ` · booked ${formatTime(entry.appointment_time)}` : ' · walk-in'}
        </p>
      </div>
      {triage && <Badge tone={triage.tone}>{triage.label}</Badge>}
      {inRoom ? (
        <Badge tone="green">With doctor</Badge>
      ) : (
        <span className="text-sm text-slate-500">waiting {waited(entry.waiting_minutes)}</span>
      )}
      {canCancel && !inRoom && (
        <Button
          size="sm"
          variant="ghost"
          loading={cancel.isPending}
          onClick={() => window.confirm(`Remove ${entry.patient.name} from the queue?`) && cancel.mutate(entry.id)}
        >
          Left
        </Button>
      )}
    </li>
  )
}

export function QueuePage() {
  const user = useCurrentUser()
  const [doctor, setDoctor] = useState<number | ''>('')
  const { data: queue, isLoading, error, dataUpdatedAt } = useQueue(doctor)
  const frontDesk = user.user_type === 'receptionist' || user.user_type === 'admin'

  return (
    <>
      <PageHeader
        title="Today's queue"
        description={dataUpdatedAt ? `Updates automatically · last at ${formatTime(new Date(dataUpdatedAt).toISOString())}` : undefined}
      />
      <Card>
        {user.user_type !== 'doctor' && (
          <div className="border-b border-slate-200 p-4 sm:max-w-sm">
            <DoctorSelect value={doctor} onChange={setDoctor} allowAll />
          </div>
        )}
        <ErrorAlert error={error} />
        {isLoading ? (
          <Spinner />
        ) : !queue?.length ? (
          <EmptyState icon={<ListOrdered className="size-6" />} title="Nobody is waiting" />
        ) : (
          <ul className="divide-y divide-slate-100">
            {queue.map((entry) => (
              <QueueRow key={entry.id} entry={entry} canCancel={frontDesk} />
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
