import { ListOrdered } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { useVisitTransition } from '@/api/clinical'

import { useCancelVisit, useQueue, type QueueEntry } from '@/api/frontDesk'
import { TriageModal, VitalsModal } from '@/components/clinical/NursingForms'
import { DoctorSelect } from '@/components/frontDesk'
import { Badge, Button, Card, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { formatTime } from '@/lib/format'
import { TRIAGE } from '@/lib/labels'
import type { Role } from '@/lib/roles'

function waited(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

function QueueRow({ entry, role }: { entry: QueueEntry; role: Role }) {
  const cancel = useCancelVisit()
  const navigate = useNavigate()
  const start = useVisitTransition(entry.id)
  const [dialog, setDialog] = useState<'triage' | 'vitals' | null>(null)
  const canCancel = role === 'receptionist' || role === 'admin'
  const triage = entry.triage_level ? TRIAGE[entry.triage_level] : null
  const inRoom = entry.status === 'in_progress'

  return (
    <li className={`flex flex-wrap items-center gap-4 px-4 py-3 ${inRoom ? 'bg-brand-50/60' : ''}`}>
      <div className="grid size-10 shrink-0 place-items-center rounded-full bg-white text-sm font-semibold text-brand-700 ring-1 ring-brand-200">
        {entry.position ?? '•'}
      </div>
      <div className="min-w-0 flex-1">
        {role === 'doctor' || role === 'nurse' ? (
          <Link to={`/visits/${entry.id}`} className="font-medium text-brand-700 hover:underline">
            {entry.patient.name}
          </Link>
        ) : (
          <p className="font-medium text-slate-900">{entry.patient.name}</p>
        )}
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
      {role === 'nurse' && (
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={() => setDialog('triage')}>
            Triage
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setDialog('vitals')}>
            Vitals
          </Button>
        </div>
      )}
      {role === 'doctor' &&
        (inRoom ? (
          <Button size="sm" variant="secondary" onClick={() => navigate(`/visits/${entry.id}`)}>
            Open
          </Button>
        ) : (
          <Button
            size="sm"
            loading={start.isPending}
            onClick={() => start.mutate('start', { onSuccess: () => navigate(`/visits/${entry.id}`) })}
          >
            Call in
          </Button>
        ))}
      {dialog === 'triage' && <TriageModal visitId={entry.id} patientName={entry.patient.name} onClose={() => setDialog(null)} />}
      {dialog === 'vitals' && <VitalsModal visitId={entry.id} patientName={entry.patient.name} onClose={() => setDialog(null)} />}
    </li>
  )
}

export function QueuePage() {
  const user = useCurrentUser()
  const [doctor, setDoctor] = useState<number | ''>('')
  const { data: queue, isLoading, error, dataUpdatedAt } = useQueue(doctor)

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
              <QueueRow key={entry.id} entry={entry} role={user.user_type} />
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
