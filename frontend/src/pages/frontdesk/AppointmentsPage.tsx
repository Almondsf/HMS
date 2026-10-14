import { CalendarDays, CalendarPlus } from 'lucide-react'
import { useState } from 'react'

import { useAppointmentAction, useAppointments, type Appointment, type AppointmentStatus } from '@/api/frontDesk'
import { DoctorSelect } from '@/components/frontDesk'
import { Badge, Button, Card, EmptyState, ErrorAlert, Input, PageHeader, Spinner } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { formatTime, todayIso } from '@/lib/format'
import { BookAppointmentModal } from '@/pages/frontdesk/BookAppointmentModal'

const STATUS: Record<AppointmentStatus, { label: string; tone: 'brand' | 'green' | 'gray' | 'red' }> = {
  scheduled: { label: 'Scheduled', tone: 'brand' },
  checked_in: { label: 'Checked in', tone: 'green' },
  cancelled: { label: 'Cancelled', tone: 'gray' },
  no_show: { label: 'No-show', tone: 'red' },
}

function AppointmentRow({ appointment, frontDesk }: { appointment: Appointment; frontDesk: boolean }) {
  const action = useAppointmentAction()
  const status = STATUS[appointment.status]
  const isToday = appointment.starts_at.slice(0, 10) === todayIso()
  const started = new Date(appointment.starts_at) < new Date()

  function run(name: 'check-in' | 'cancel' | 'no-show') {
    if (name === 'cancel') {
      const reason = window.prompt('Reason for cancelling (optional)') ?? undefined
      if (reason === undefined) return
      action.mutate({ id: appointment.id, action: name, reason })
    } else {
      action.mutate({ id: appointment.id, action: name })
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-4 px-4 py-3">
      <div className="w-24 shrink-0">
        <p className="font-medium text-slate-900">{formatTime(appointment.starts_at)}</p>
        <p className="text-xs text-slate-500">{appointment.duration_minutes} min</p>
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-900">{appointment.patient_name}</p>
        <p className="text-xs text-slate-500">
          {appointment.patient_mrn} · Dr {appointment.doctor_name}
          {appointment.reason ? ` · ${appointment.reason}` : ''}
        </p>
        {action.error && <p className="mt-1 text-xs text-red-600">{action.error.message}</p>}
      </div>
      <Badge tone={status.tone}>{status.label}</Badge>
      {frontDesk && appointment.status === 'scheduled' && (
        <div className="flex gap-2">
          {isToday && (
            <Button size="sm" loading={action.isPending} onClick={() => run('check-in')}>
              Check in
            </Button>
          )}
          {started && (
            <Button size="sm" variant="secondary" onClick={() => run('no-show')}>
              No-show
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => run('cancel')}>
            Cancel
          </Button>
        </div>
      )}
    </li>
  )
}

export function AppointmentsPage() {
  const user = useCurrentUser()
  const frontDesk = user.user_type === 'receptionist' || user.user_type === 'admin'
  const [date, setDate] = useState(todayIso())
  const [doctor, setDoctor] = useState<number | ''>('')
  const [booking, setBooking] = useState(false)
  const { data: appointments, isLoading, error } = useAppointments({ date, doctor })

  return (
    <>
      <PageHeader
        title="Appointments"
        actions={
          frontDesk && (
            <Button icon={<CalendarPlus className="size-4" />} onClick={() => setBooking(true)}>
              Book appointment
            </Button>
          )
        }
      />
      <Card>
        <div className="grid gap-4 border-b border-slate-200 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <Input label="Day" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          {user.user_type !== 'doctor' && <DoctorSelect value={doctor} onChange={setDoctor} allowAll />}
        </div>
        <ErrorAlert error={error} />
        {isLoading ? (
          <Spinner />
        ) : !appointments?.length ? (
          <EmptyState icon={<CalendarDays className="size-6" />} title="No appointments on this day" />
        ) : (
          <ul className="divide-y divide-slate-100">
            {appointments.map((appointment) => (
              <AppointmentRow key={appointment.id} appointment={appointment} frontDesk={frontDesk} />
            ))}
          </ul>
        )}
      </Card>
      {booking && <BookAppointmentModal open onClose={() => setBooking(false)} date={date} doctor={doctor} />}
    </>
  )
}
