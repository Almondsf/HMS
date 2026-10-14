import { CalendarPlus, DoorOpen, Pencil } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router'

import { fullName, useOpenVisit, usePatient, useSavePatient } from '@/api/frontDesk'
import { DoctorSelect, PatientForm } from '@/components/frontDesk'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useCurrentUser } from '@/lib/auth'
import { age, formatDate, titleCase } from '@/lib/format'
import { BookAppointmentModal } from '@/pages/frontdesk/BookAppointmentModal'

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{value || '—'}</dd>
    </div>
  )
}

function WalkInModal({ patientId, open, onClose }: { patientId: number; open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const openVisit = useOpenVisit()
  const [doctor, setDoctor] = useState<number | ''>('')
  const [reason, setReason] = useState('')
  const errors = openVisit.error instanceof ApiError ? openVisit.error.fieldErrors : {}

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (doctor === '') return
    openVisit.mutate(
      { patient: patientId, assigned_doctor: doctor, reason_for_visit: reason },
      { onSuccess: () => navigate('/queue') },
    )
  }

  return (
    <Modal open={open} title="Walk-in visit" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={Object.keys(errors).length ? null : openVisit.error} />
        <DoctorSelect value={doctor} onChange={setDoctor} error={errors.assigned_doctor} />
        <Input
          label="Reason for visit"
          required
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          error={errors.reason_for_visit}
        />
        <div className="flex justify-end">
          <Button type="submit" loading={openVisit.isPending} disabled={doctor === ''}>
            Add to queue
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function PatientDetailPage() {
  const { id } = useParams()
  const user = useCurrentUser()
  const patientId = Number(id)
  const { data: patient, isLoading, error } = usePatient(patientId)
  const save = useSavePatient(patientId)
  const [editing, setEditing] = useState(false)
  const [walkIn, setWalkIn] = useState(false)
  const [booking, setBooking] = useState(false)
  const frontDesk = user.user_type === 'receptionist' || user.user_type === 'admin'

  if (isLoading) return <Spinner />
  if (!patient) return <ErrorAlert error={error ?? new Error('Patient not found.')} />

  const years = age(patient.user.date_of_birth)

  return (
    <>
      <PageHeader
        title={fullName(patient.user)}
        description={`${patient.mrn}${years !== null ? ` · ${years} years` : ''}${
          patient.user.gender ? ` · ${titleCase(patient.user.gender)}` : ''
        }`}
        actions={
          frontDesk && (
            <>
              <Button variant="secondary" icon={<Pencil className="size-4" />} onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button variant="secondary" icon={<CalendarPlus className="size-4" />} onClick={() => setBooking(true)}>
                Book appointment
              </Button>
              <Button icon={<DoorOpen className="size-4" />} onClick={() => setWalkIn(true)}>
                Walk-in visit
              </Button>
            </>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-4 font-medium text-slate-900">Contact</h2>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Detail label="Phone" value={patient.user.phone_number} />
            <Detail label="Email" value={patient.user.email} />
            <Detail label="Date of birth" value={formatDate(patient.user.date_of_birth)} />
            <Detail label="Address" value={patient.user.address} />
            <Detail label="Emergency contact" value={patient.user.emergency_contact} />
            <Detail label="Emergency phone" value={patient.user.emergency_phone} />
          </dl>
        </Card>
        <Card className="p-5">
          <h2 className="mb-4 font-medium text-slate-900">Clinical background</h2>
          <dl className="space-y-4">
            <div className="flex gap-2">
              {patient.blood_group && <Badge tone="red">{patient.blood_group}</Badge>}
              {patient.genotype && <Badge tone={patient.genotype === 'SS' ? 'amber' : 'gray'}>{patient.genotype}</Badge>}
            </div>
            <Detail label="Allergies" value={patient.allergies} />
            <Detail label="Medical history" value={patient.medical_history} />
          </dl>
        </Card>
      </div>

      <Modal open={editing} title="Edit patient" onClose={() => setEditing(false)} wide>
        <PatientForm
          initial={patient}
          submitLabel="Save changes"
          submitting={save.isPending}
          error={save.error}
          onSubmit={(input) => save.mutate(input, { onSuccess: () => setEditing(false) })}
        />
      </Modal>
      {walkIn && <WalkInModal patientId={patient.id} open onClose={() => setWalkIn(false)} />}
      {booking && <BookAppointmentModal open onClose={() => setBooking(false)} patient={patient} />}
    </>
  )
}
