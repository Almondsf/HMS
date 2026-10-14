import { Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import {
  useDrugSearch,
  useIcdSearch,
  useLabCatalogue,
  useRecordConsultation,
  type ConsultationInput,
  type Diagnosis,
  type Drug,
} from '@/api/clinical'
import { useDebounced } from '@/components/frontDesk'
import { Button, Card, ErrorAlert, Input, Textarea, cx } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatMoney } from '@/lib/hospital'

type DiagnosisRow = ConsultationInput['diagnoses'][number]
type PrescriptionRow = ConsultationInput['prescriptions'][number] & { key: number }

let nextKey = 1

function emptyPrescription(drug?: Drug): PrescriptionRow {
  return {
    key: nextKey++,
    drug: drug?.id ?? null,
    medication_name: drug?.name ?? '',
    dosage: '',
    frequency: '',
    duration: '',
    quantity: null,
    instructions: '',
  }
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-brand-700">{title}</h3>
      {children}
    </section>
  )
}

/** Search ICD-10 and add coded diagnoses (or a free-text one). */
function DiagnosesEditor({ rows, onChange }: { rows: DiagnosisRow[]; onChange: (rows: DiagnosisRow[]) => void }) {
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search)
  const { data: codes } = useIcdSearch(debounced)

  function add(row: Omit<DiagnosisRow, 'kind' | 'certainty'>) {
    // The first diagnosis is primary, the rest secondary
    const kind: Diagnosis['kind'] = rows.some((existing) => existing.kind === 'primary') ? 'secondary' : 'primary'
    onChange([...rows, { ...row, kind, certainty: 'provisional' }])
    setSearch('')
  }

  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <div key={`${row.code}-${index}`} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 p-2">
          <span className="font-mono text-xs text-brand-700">{row.code ?? 'free text'}</span>
          <span className="min-w-0 flex-1 text-sm text-slate-900">{row.description}</span>
          <select
            aria-label="Kind"
            value={row.kind}
            onChange={(event) =>
              onChange(rows.map((r, i) => (i === index ? { ...r, kind: event.target.value as Diagnosis['kind'] } : r)))
            }
            className="rounded-md border border-slate-200 px-2 py-1 text-xs"
          >
            <option value="primary">Primary</option>
            <option value="secondary">Secondary</option>
          </select>
          <select
            aria-label="Certainty"
            value={row.certainty}
            onChange={(event) =>
              onChange(
                rows.map((r, i) => (i === index ? { ...r, certainty: event.target.value as Diagnosis['certainty'] } : r)),
              )
            }
            className="rounded-md border border-slate-200 px-2 py-1 text-xs"
          >
            <option value="provisional">Provisional</option>
            <option value="confirmed">Confirmed</option>
          </select>
          <button
            type="button"
            onClick={() => onChange(rows.filter((_, i) => i !== index))}
            className="rounded p-1 text-slate-400 hover:text-red-600"
            aria-label="Remove diagnosis"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ))}
      <div className="relative">
        <Input
          label="Add diagnosis"
          placeholder="Search ICD-10, e.g. malaria or B54"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        {debounced.trim().length >= 2 && (
          <ul className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
            {codes?.map((code) => (
              <li key={code.code}>
                <button
                  type="button"
                  onClick={() => add({ code: code.code, description: code.title })}
                  className="flex w-full gap-3 px-3 py-2 text-left text-sm hover:bg-brand-50"
                >
                  <span className="w-14 shrink-0 font-mono text-xs text-brand-700">{code.code}</span>
                  {code.title}
                </button>
              </li>
            ))}
            <li>
              <button
                type="button"
                onClick={() => add({ code: null, description: search.trim() })}
                className="w-full px-3 py-2 text-left text-sm text-slate-600 hover:bg-brand-50"
              >
                Use “{search.trim()}” as a free-text diagnosis
              </button>
            </li>
          </ul>
        )}
      </div>
    </div>
  )
}

function PrescriptionsEditor({ rows, onChange }: { rows: PrescriptionRow[]; onChange: (rows: PrescriptionRow[]) => void }) {
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search)
  const { data: drugs } = useDrugSearch(debounced)
  const update = (key: number, changes: Partial<PrescriptionRow>) =>
    onChange(rows.map((row) => (row.key === key ? { ...row, ...changes } : row)))

  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <div key={row.key} className="space-y-3 rounded-lg border border-slate-200 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-slate-900">
              {row.medication_name || 'Medication'}
              {!row.drug && <span className="ml-2 text-xs font-normal text-amber-700">not in the formulary</span>}
            </p>
            <button
              type="button"
              onClick={() => onChange(rows.filter((r) => r.key !== row.key))}
              className="rounded p-1 text-slate-400 hover:text-red-600"
              aria-label="Remove prescription"
            >
              <Trash2 className="size-4" />
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <Input label="Dose" required placeholder="500mg" value={row.dosage} onChange={(e) => update(row.key, { dosage: e.target.value })} />
            <Input label="Frequency" required placeholder="TDS" value={row.frequency} onChange={(e) => update(row.key, { frequency: e.target.value })} />
            <Input label="Duration" required placeholder="5 days" value={row.duration} onChange={(e) => update(row.key, { duration: e.target.value })} />
            <Input
              label="Quantity"
              type="number"
              min={1}
              value={row.quantity ?? ''}
              onChange={(e) => update(row.key, { quantity: e.target.value ? Number(e.target.value) : null })}
            />
          </div>
          <Input label="Instructions" placeholder="After meals" value={row.instructions} onChange={(e) => update(row.key, { instructions: e.target.value })} />
        </div>
      ))}
      <div className="relative">
        <Input
          label="Add medication"
          placeholder="Search the drug list"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        {debounced.trim().length >= 2 && (
          <ul className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
            {drugs?.map((drug) => (
              <li key={drug.id}>
                <button
                  type="button"
                  onClick={() => {
                    onChange([...rows, emptyPrescription(drug)])
                    setSearch('')
                  }}
                  className="flex w-full justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-brand-50"
                >
                  <span>{drug.name}</span>
                  <span className={cx('text-xs', drug.quantity_in_stock > 0 ? 'text-slate-500' : 'text-red-600')}>
                    {drug.quantity_in_stock > 0 ? `${drug.quantity_in_stock} ${drug.unit} in stock` : 'out of stock'}
                  </span>
                </button>
              </li>
            ))}
            <li>
              <button
                type="button"
                onClick={() => {
                  onChange([...rows, { ...emptyPrescription(), medication_name: search.trim() }])
                  setSearch('')
                }}
                className="w-full px-3 py-2 text-left text-sm text-slate-600 hover:bg-brand-50"
              >
                Prescribe “{search.trim()}” (not stocked here)
              </button>
            </li>
          </ul>
        )}
      </div>
    </div>
  )
}

function LabTestsPicker({ selected, onChange }: { selected: number[]; onChange: (ids: number[]) => void }) {
  const { data: tests, isLoading } = useLabCatalogue(true)
  if (isLoading) return <p className="text-sm text-slate-500">Loading tests…</p>
  if (!tests?.length) return <p className="text-sm text-slate-500">The lab hasn't set up its test list yet.</p>
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {tests.map((test) => (
        <label key={test.id} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
          <input
            type="checkbox"
            checked={selected.includes(test.id)}
            onChange={(event) =>
              onChange(event.target.checked ? [...selected, test.id] : selected.filter((id) => id !== test.id))
            }
            className="accent-brand-500"
          />
          <span className="flex-1">{test.name}</span>
          <span className="text-xs text-slate-500">{formatMoney(test.cost)}</span>
        </label>
      ))}
    </div>
  )
}

export function ConsultationForm({ visitId, labEnabled, onSaved }: { visitId: number; labEnabled: boolean; onSaved: () => void }) {
  const record = useRecordConsultation(visitId)
  const [notes, setNotes] = useState({ subjective: '', objective: '', assessment: '', plan: '' })
  const [diagnoses, setDiagnoses] = useState<DiagnosisRow[]>([])
  const [prescriptions, setPrescriptions] = useState<PrescriptionRow[]>([])
  const [labTests, setLabTests] = useState<number[]>([])
  const [labReason, setLabReason] = useState('')
  const [followUp, setFollowUp] = useState('')
  const fieldErrors = record.error instanceof ApiError ? record.error.fieldErrors : {}

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    record.mutate(
      {
        visit: visitId,
        ...notes,
        follow_up_date: followUp ? new Date(`${followUp}T09:00:00`).toISOString() : null,
        diagnoses,
        prescriptions: prescriptions.map(({ key: _key, ...prescription }) => prescription),
        lab_tests: labTests,
        lab_reason: labReason,
      },
      { onSuccess: onSaved },
    )
  }

  return (
    <Card className="p-5">
      <form onSubmit={handleSubmit} className="space-y-6">
        <h2 className="text-lg font-semibold text-slate-900">New consultation</h2>
        <ErrorAlert error={record.error} />
        <Section title="Notes (SOAP)">
          <Textarea label="Subjective" placeholder="Complaints, symptoms, history" value={notes.subjective} onChange={(e) => setNotes({ ...notes, subjective: e.target.value })} />
          <Textarea label="Objective" placeholder="Examination findings" value={notes.objective} onChange={(e) => setNotes({ ...notes, objective: e.target.value })} />
          <Textarea label="Assessment" placeholder="Clinical impression" value={notes.assessment} onChange={(e) => setNotes({ ...notes, assessment: e.target.value })} />
          <Textarea label="Plan" placeholder="Treatment and advice" value={notes.plan} onChange={(e) => setNotes({ ...notes, plan: e.target.value })} />
        </Section>
        <Section title="Diagnoses">
          <DiagnosesEditor rows={diagnoses} onChange={setDiagnoses} />
          {fieldErrors.diagnoses && <p className="text-sm text-red-600">{fieldErrors.diagnoses}</p>}
        </Section>
        <Section title="Prescriptions">
          <PrescriptionsEditor rows={prescriptions} onChange={setPrescriptions} />
        </Section>
        {labEnabled && (
          <Section title="Lab tests">
            <LabTestsPicker selected={labTests} onChange={setLabTests} />
            {labTests.length > 0 && (
              <Input label="Reason for tests" value={labReason} onChange={(e) => setLabReason(e.target.value)} />
            )}
          </Section>
        )}
        <Section title="Follow-up">
          <div className="sm:max-w-xs">
            <Input label="Follow-up date" type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
          </div>
        </Section>
        <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
          <Button type="submit" loading={record.isPending} icon={<Plus className="size-4" />}>
            Save consultation
          </Button>
        </div>
      </form>
    </Card>
  )
}
