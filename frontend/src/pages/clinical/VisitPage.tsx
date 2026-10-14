import { Activity, AlertTriangle, CheckCircle2, ClipboardList, PlayCircle, Siren } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { useVisit, useVisitTransition, type Consultation } from '@/api/clinical'
import { fullName, usePatient } from '@/api/frontDesk'
import { ConsultationForm } from '@/components/clinical/ConsultationForm'
import { TriageModal, VitalsModal, VitalsSummary } from '@/components/clinical/NursingForms'
import { Badge, Button, Card, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { age, formatDate, formatDateTime, titleCase } from '@/lib/format'
import { useHospital } from '@/lib/hospital'
import { TRIAGE, VISIT_STATUS } from '@/lib/labels'

function ConsultationCard({ consultation }: { consultation: Consultation }) {
  const notes = [
    ['Subjective', consultation.subjective],
    ['Objective', consultation.objective],
    ['Assessment', consultation.assessment],
    ['Plan', consultation.plan],
  ].filter(([, text]) => text)

  return (
    <Card className="space-y-4 p-5">
      <p className="text-xs text-slate-500">{formatDateTime(consultation.created_at)}</p>
      {consultation.diagnoses.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {consultation.diagnoses.map((diagnosis) => (
            <Badge key={diagnosis.id} tone={diagnosis.certainty === 'ruled_out' ? 'gray' : diagnosis.kind === 'primary' ? 'brand' : 'gray'}>
              {diagnosis.code ? `${diagnosis.code} · ` : ''}
              {diagnosis.description}
              {diagnosis.certainty !== 'confirmed' ? ` (${titleCase(diagnosis.certainty)})` : ''}
            </Badge>
          ))}
        </div>
      )}
      {notes.length > 0 && (
        <dl className="grid gap-3 sm:grid-cols-2">
          {notes.map(([label, text]) => (
            <div key={label}>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
              <dd className="mt-0.5 whitespace-pre-line text-sm text-slate-800">{text}</dd>
            </div>
          ))}
        </dl>
      )}
      {consultation.prescriptions.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Prescriptions</p>
          <ul className="space-y-1 text-sm text-slate-800">
            {consultation.prescriptions.map((prescription) => (
              <li key={prescription.id}>
                {prescription.medication_name} — {prescription.dosage}, {prescription.frequency}, {prescription.duration}
                {prescription.quantity ? ` (×${prescription.quantity})` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
      {consultation.lab_orders.map((order) => (
        <div key={order.id}>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Lab · {titleCase(order.status)}</p>
          <ul className="space-y-1 text-sm text-slate-800">
            {order.results.map((result) => (
              <li key={result.id} className="flex justify-between gap-4">
                <span>{result.test_name}</span>
                <span className={result.result_value ? 'font-medium' : 'text-slate-500'}>
                  {result.result_value || titleCase(result.status)}
                  {result.normal_range && result.result_value ? ` (normal ${result.normal_range})` : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {consultation.follow_up_date && (
        <p className="text-sm text-slate-600">Follow-up: {formatDate(consultation.follow_up_date)}</p>
      )}
    </Card>
  )
}

export function VisitPage() {
  const { id } = useParams()
  const visitId = Number(id)
  const user = useCurrentUser()
  const { data: hospital } = useHospital()
  const { data: visit, isLoading, error } = useVisit(visitId)
  const { data: patient } = usePatient(visit?.patient)
  const transition = useVisitTransition(visitId)
  const [dialog, setDialog] = useState<'triage' | 'vitals' | null>(null)
  const [writing, setWriting] = useState(false)

  if (isLoading) return <Spinner />
  if (!visit) return <ErrorAlert error={error ?? new Error('Visit not found.')} />

  const isDoctor = user.user_type === 'doctor'
  const isNurse = user.user_type === 'nurse'
  const open = visit.status === 'waiting' || visit.status === 'in_progress'
  const status = VISIT_STATUS[visit.status]
  const name = patient ? fullName(patient.user) : 'Patient'
  const years = patient ? age(patient.user.date_of_birth) : null

  return (
    <>
      <PageHeader
        title={name}
        description={[
          patient?.mrn,
          years !== null ? `${years} years` : null,
          patient?.user.gender ? titleCase(patient.user.gender) : null,
          `Visit ${formatDateTime(visit.visit_date)}`,
        ]
          .filter(Boolean)
          .join(' · ')}
        actions={
          <>
            {(isNurse || isDoctor) && open && (
              <>
                <Button variant="secondary" icon={<Siren className="size-4" />} onClick={() => setDialog('triage')}>
                  Triage
                </Button>
                <Button variant="secondary" icon={<Activity className="size-4" />} onClick={() => setDialog('vitals')}>
                  Vitals
                </Button>
              </>
            )}
            {isDoctor && visit.status === 'waiting' && (
              <Button icon={<PlayCircle className="size-4" />} loading={transition.isPending} onClick={() => transition.mutate('start')}>
                Start consultation
              </Button>
            )}
            {isDoctor && open && (
              <Button
                variant={visit.status === 'in_progress' ? 'primary' : 'secondary'}
                icon={<CheckCircle2 className="size-4" />}
                loading={transition.isPending}
                onClick={() => window.confirm('Complete this visit?') && transition.mutate('complete')}
              >
                Complete visit
              </Button>
            )}
          </>
        }
      />
      <ErrorAlert error={transition.error} />

      {/* Safety banner: things a clinician must not miss */}
      {patient && (patient.allergies || patient.genotype === 'SS') && (
        <div role="alert" className="mb-6 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div>
            {patient.allergies && (
              <p>
                <strong>Allergies:</strong> {patient.allergies}
              </p>
            )}
            {patient.genotype === 'SS' && <p><strong>Sickle cell disease</strong> (genotype SS)</p>}
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {visit.consultations.length === 0 && !writing && (
            <Card className="p-5 text-sm text-slate-500">No consultation recorded for this visit yet.</Card>
          )}
          {visit.consultations.map((consultation) => (
            <ConsultationCard key={consultation.id} consultation={consultation} />
          ))}
          {isDoctor && visit.status !== 'cancelled' && (
            writing ? (
              <ConsultationForm
                visitId={visit.id}
                labEnabled={hospital?.features.includes('lab') ?? false}
                onSaved={() => setWriting(false)}
              />
            ) : (
              <Button icon={<ClipboardList className="size-4" />} onClick={() => setWriting(true)}>
                Record consultation
              </Button>
            )
          )}
        </div>

        <div className="space-y-6">
          <Card className="space-y-3 p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-medium text-slate-900">Visit</h2>
              <Badge tone={status.tone}>{status.label}</Badge>
            </div>
            <p className="text-sm text-slate-700">{visit.reason_for_visit}</p>
            {visit.triage_level && (
              <div className="space-y-1">
                <Badge tone={TRIAGE[visit.triage_level].tone}>{TRIAGE[visit.triage_level].label}</Badge>
                {visit.triage_notes && <p className="text-sm text-slate-600">{visit.triage_notes}</p>}
              </div>
            )}
            {patient && (
              <Link to={`/patients/${patient.id}`} className="text-sm font-medium text-brand-600 hover:text-brand-700">
                Patient record →
              </Link>
            )}
          </Card>
          <Card className="p-5">
            <h2 className="mb-3 font-medium text-slate-900">Vital signs</h2>
            <VitalsSummary vitals={visit.vitals} />
          </Card>
        </div>
      </div>

      {dialog === 'triage' && <TriageModal visitId={visit.id} patientName={name} onClose={() => setDialog(null)} />}
      {dialog === 'vitals' && <VitalsModal visitId={visit.id} patientName={name} onClose={() => setDialog(null)} />}
    </>
  )
}
