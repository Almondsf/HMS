import { useState, type FormEvent } from 'react'

import { useBookAppointment, type Patient } from '@/api/frontDesk'
import { DoctorSelect, PatientPicker } from '@/components/frontDesk'
import { Modal } from '@/components/Modal'
import { Button, ErrorAlert, Input, Select } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { todayIso } from '@/lib/format'

export function BookAppointmentModal({
  open,
  onClose,
  patient: fixedPatient,
  date,
  doctor: defaultDoctor,
}: {
  open: boolean
  onClose: () => void
  patient?: Patient
  date?: string
  doctor?: number | ''
}) {
  const book = useBookAppointment()
  const [patient, setPatient] = useState<Patient | null>(fixedPatient ?? null)
  const [doctor, setDoctor] = useState<number | ''>(defaultDoctor ?? '')
  const [day, setDay] = useState(date ?? todayIso())
  const [time, setTime] = useState('09:00')
  const [duration, setDuration] = useState(15)
  const [reason, setReason] = useState('')
  const errors = book.error instanceof ApiError ? book.error.fieldErrors : {}

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!patient || doctor === '') return
    book.mutate(
      {
        patient: patient.id,
        doctor,
        // Local wall-clock time; the browser adds the offset
        starts_at: new Date(`${day}T${time}:00`).toISOString(),
        duration_minutes: duration,
        reason,
      },
      {
        onSuccess: () => {
          book.reset()
          onClose()
        },
      },
    )
  }

  return (
    <Modal open={open} title="Book appointment" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={Object.keys(errors).length ? null : book.error} />
        {fixedPatient ? null : <PatientPicker value={patient} onChange={setPatient} error={errors.patient} />}
        <DoctorSelect value={doctor} onChange={setDoctor} error={errors.doctor} />
        <div className="grid gap-4 sm:grid-cols-3">
          <Input label="Date" type="date" required min={todayIso()} value={day} onChange={(e) => setDay(e.target.value)} />
          <Input
            label="Time"
            type="time"
            required
            step={300}
            value={time}
            onChange={(e) => setTime(e.target.value)}
            error={errors.starts_at}
          />
          <Select
            label="Length"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            error={errors.duration_minutes}
          >
            {[10, 15, 20, 30, 45, 60].map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes} min
              </option>
            ))}
          </Select>
        </div>
        <Input label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Follow-up" />
        <div className="flex justify-end">
          <Button type="submit" loading={book.isPending} disabled={!patient || doctor === ''}>
            Book
          </Button>
        </div>
      </form>
    </Modal>
  )
}
