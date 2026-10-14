import { AlertTriangle } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { VITAL_FIELDS, useRecordVitals, useTriage, type VitalKey, type Vitals } from '@/api/clinical'
import type { TriageLevel } from '@/api/frontDesk'
import { Modal } from '@/components/Modal'
import { Badge, Button, ErrorAlert, Input, Textarea, cx } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatTime } from '@/lib/format'
import { TRIAGE } from '@/lib/labels'

export function TriageModal({ visitId, patientName, onClose }: { visitId: number; patientName: string; onClose: () => void }) {
  const triage = useTriage(visitId)
  const [level, setLevel] = useState<TriageLevel>('standard')
  const [notes, setNotes] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    triage.mutate({ triage_level: level, triage_notes: notes }, { onSuccess: onClose })
  }

  return (
    <Modal open title={`Triage · ${patientName}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={triage.error} />
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-slate-700">Priority</legend>
          <div className="grid grid-cols-2 gap-2">
            {(Object.keys(TRIAGE) as TriageLevel[]).map((option) => (
              <label
                key={option}
                className={cx(
                  'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm',
                  level === option ? 'border-brand-500 bg-brand-50' : 'border-slate-200 hover:bg-slate-50',
                )}
              >
                <input
                  type="radio"
                  name="triage"
                  value={option}
                  checked={level === option}
                  onChange={() => setLevel(option)}
                  className="accent-brand-500"
                />
                <Badge tone={TRIAGE[option].tone}>{TRIAGE[option].label}</Badge>
              </label>
            ))}
          </div>
        </fieldset>
        <Textarea label="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
        <div className="flex justify-end">
          <Button type="submit" loading={triage.isPending}>
            Save triage
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function VitalsModal({ visitId, patientName, onClose }: { visitId: number; patientName: string; onClose: () => void }) {
  const record = useRecordVitals(visitId)
  const [values, setValues] = useState<Partial<Record<VitalKey, string>>>({})
  const [notes, setNotes] = useState('')
  const errors = record.error instanceof ApiError ? record.error.fieldErrors : {}

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const filled = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '' && value !== undefined))
    record.mutate({ ...filled, notes }, { onSuccess: onClose })
  }

  return (
    <Modal open title={`Vital signs · ${patientName}`} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={Object.keys(errors).length ? null : record.error} />
        <p className="text-sm text-slate-500">Fill in what you measured; everything is optional.</p>
        <div className="grid gap-4 sm:grid-cols-3">
          {VITAL_FIELDS.map((field) => (
            <Input
              key={field.key}
              label={field.unit ? `${field.label} (${field.unit})` : field.label}
              type="number"
              inputMode="decimal"
              step={field.step}
              value={values[field.key] ?? ''}
              onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))}
              error={errors[field.key]}
            />
          ))}
        </div>
        <Textarea label="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
        <div className="flex justify-end">
          <Button type="submit" loading={record.isPending}>
            Save vitals
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** The latest set of vitals, with abnormal values called out. */
export function VitalsSummary({ vitals }: { vitals: Vitals[] }) {
  const latest = vitals[0]
  if (!latest) return <p className="text-sm text-slate-500">No vitals recorded yet.</p>

  const shown = VITAL_FIELDS.filter((field) => latest[field.key] !== null && latest[field.key] !== '')
  return (
    <div className="space-y-3">
      {latest.flags.length > 0 && (
        <div
          className={cx(
            'flex items-start gap-2 rounded-lg p-3 text-sm',
            latest.is_critical ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800',
          )}
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {latest.is_critical ? 'Critical: ' : ''}
            {latest.flags.join(', ')}
          </span>
        </div>
      )}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {shown.map((field) => (
          <div key={field.key} className="rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-xs text-slate-500">{field.label}</dt>
            <dd className="text-sm font-medium text-slate-900">
              {latest[field.key]} {field.unit}
            </dd>
          </div>
        ))}
        {latest.bmi !== null && (
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-xs text-slate-500">BMI</dt>
            <dd className="text-sm font-medium text-slate-900">{latest.bmi}</dd>
          </div>
        )}
      </dl>
      <p className="text-xs text-slate-500">
        Recorded {formatTime(latest.recorded_at)}
        {latest.recorded_by_name ? ` by ${latest.recorded_by_name}` : ''}
        {vitals.length > 1 ? ` · ${vitals.length - 1} earlier set(s)` : ''}
      </p>
    </div>
  )
}
