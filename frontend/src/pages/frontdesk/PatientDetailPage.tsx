import { CalendarPlus, DoorOpen, Pencil } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { usePatientVisits } from '@/api/clinical'

import { fullName, useOpenVisit, usePatient, useSavePatient } from '@/api/frontDesk'
import { DoctorSelect, PatientForm } from '@/components/frontDesk'
import { InsuranceCover } from '@/components/InsuranceCover'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useCurrentUser } from '@/lib/auth'
import { age, formatDate, formatDateTime, titleCase } from '@/lib/format'
import { useHospital } from '@/lib/hospital'
import { VISIT_STATUS } from '@/lib/labels'
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

function VisitHistory({ patientId }: { patientId: number }) {
  const { data: visits, isLoading } = usePatientVisits(patientId, true)
  return (
    <Card className="mt-6">
      <h2 className="border-b border-slate-200 p-5 font-medium text-slate-900">Visits</h2>
      {isLoading ? (
        <Spinner />
      ) : !visits?.length ? (
        <p className="p-5 text-sm text-slate-500">No visits yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {visits.map((visit) => {
            const diagnoses = visit.consultations.flatMap((consultation) => consultation.diagnoses)
            return (
              <li key={visit.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <Link to={`/visits/${visit.id}`} className="w-40 shrink-0 text-sm font-medium text-brand-700 hover:underline">
                  {formatDateTime(visit.visit_date)}
                </Link>
                <span className="min-w-0 flex-1 text-sm text-slate-700">
                  {visit.reason_for_visit}
                  {diagnoses.length > 0 && (
                    <span className="text-slate-500"> · {diagnoses.map((d) => d.code ?? d.description).join(', ')}</span>
                  )}
                </span>
                <Badge tone={VISIT_STATUS[visit.status].tone}>{VISIT_STATUS[visit.status].label}</Badge>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

export function PatientDetailPage() {
  const { id } = useParams()
  const user = useCurrentUser()
  const patientId = Number(id)
  const { data: hospital } = useHospital()
  const { data: patient, isLoading, error } = usePatient(patientId)
  const save = useSavePatient(patientId)
  const [editing, setEditing] = useState(false)
  const [walkIn, setWalkIn] = useState(false)
  const [booking, setBooking] = useState(false)
  const frontDesk = user.user_type === 'receptionist' || user.user_type === 'admin'
  const clinician = user.user_type === 'doctor' || user.user_type === 'nurse' || user.user_type === 'admin'

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

      {hospital?.features.includes('insurance') && frontDesk && (
        <div className="mt-6 lg:w-1/3">
          <InsuranceCover patientId={patient.id} canEdit={frontDesk} />
        </div>
      )}
      {clinician && <VisitHistory patientId={patient.id} />}

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
