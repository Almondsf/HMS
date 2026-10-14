import { Pill } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { useDrugs, useDispense, usePendingPrescriptions, type PendingPrescription } from '@/api/labPharmacy'
import { Modal } from '@/components/Modal'
import { Button, Card, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { formatDateTime } from '@/lib/format'

function remaining(prescription: PendingPrescription): number {
  return prescription.quantity !== null ? prescription.quantity - prescription.quantity_dispensed : 1
}

interface Line {
  include: boolean
  drug: number | ''
  quantity: number
}

function DispenseModal({ patientName, prescriptions, onClose }: { patientName: string; prescriptions: PendingPrescription[]; onClose: () => void }) {
  const dispense = useDispense()
  const { data: drugs } = useDrugs({})
  const [lines, setLines] = useState<Record<number, Line>>(() =>
    Object.fromEntries(
      prescriptions.map((prescription) => [
        prescription.id,
        { include: true, drug: prescription.drug ?? '', quantity: Math.max(remaining(prescription), 1) },
      ]),
    ),
  )
  const update = (id: number, changes: Partial<Line>) => setLines((current) => ({ ...current, [id]: { ...current[id], ...changes } }))
  const chosen = prescriptions.filter((prescription) => lines[prescription.id].include)
  const ready = chosen.length > 0 && chosen.every((prescription) => lines[prescription.id].drug !== '')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    dispense.mutate(
      chosen.map((prescription) => ({
        prescription: prescription.id,
        drug: lines[prescription.id].drug as number,
        quantity_dispensed: lines[prescription.id].quantity,
      })),
      { onSuccess: onClose },
    )
  }

  return (
    <Modal open title={`Dispense · ${patientName}`} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={dispense.error} />
        <ul className="space-y-3">
          {prescriptions.map((prescription) => {
            const line = lines[prescription.id]
            const stock = drugs?.find((drug) => drug.id === line.drug)
            return (
              <li key={prescription.id} className="rounded-lg border border-slate-200 p-3">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1 accent-brand-500"
                    checked={line.include}
                    onChange={(event) => update(prescription.id, { include: event.target.checked })}
                  />
                  <span className="flex-1">
                    <span className="block text-sm font-medium text-slate-900">{prescription.medication_name}</span>
                    <span className="block text-xs text-slate-500">
                      {prescription.dosage} · {prescription.frequency} · {prescription.duration}
                      {prescription.quantity !== null && ` · ${remaining(prescription)} of ${prescription.quantity} left to give`}
                      {prescription.instructions ? ` · ${prescription.instructions}` : ''}
                    </span>
                  </span>
                </label>
                {line.include && (
                  <div className="mt-3 grid gap-3 pl-7 sm:grid-cols-2">
                    {prescription.drug === null ? (
                      <select
                        aria-label="Drug to dispense"
                        value={line.drug}
                        onChange={(event) => update(prescription.id, { drug: event.target.value ? Number(event.target.value) : '' })}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      >
                        <option value="">Choose the drug given…</option>
                        {drugs?.map((drug) => (
                          <option key={drug.id} value={drug.id}>
                            {drug.name} ({drug.quantity_in_stock} {drug.unit})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p className="self-center text-xs text-slate-500">
                        {stock ? `${stock.quantity_in_stock} ${stock.unit} in stock` : ''}
                      </p>
                    )}
                    <input
                      type="number"
                      min={1}
                      aria-label="Quantity"
                      value={line.quantity}
                      onChange={(event) => update(prescription.id, { quantity: Number(event.target.value) })}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
        <div className="flex justify-end">
          <Button type="submit" loading={dispense.isPending} disabled={!ready}>
            Dispense
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function PharmacyPage() {
  const { data: prescriptions, isLoading, error } = usePendingPrescriptions()
  const [dispensingFor, setDispensingFor] = useState<number | null>(null)

  // One card per patient: a pharmacist serves a patient, not a prescription
  const byPatient = useMemo(() => {
    const groups = new Map<number, { name: string; items: PendingPrescription[] }>()
    for (const prescription of prescriptions ?? []) {
      const group = groups.get(prescription.patient) ?? { name: prescription.patient_name, items: [] }
      group.items.push(prescription)
      groups.set(prescription.patient, group)
    }
    return [...groups.entries()]
  }, [prescriptions])

  const active = byPatient.find(([patientId]) => patientId === dispensingFor)

  return (
    <>
      <PageHeader
        title="Pharmacy queue"
        description="Prescriptions with medication still to give."
        actions={
          <Link to="/pharmacy/drugs" className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
            Drugs & stock
          </Link>
        }
      />
      <ErrorAlert error={error} />
      {isLoading ? (
        <Spinner />
      ) : byPatient.length === 0 ? (
        <Card>
          <EmptyState icon={<Pill className="size-6" />} title="No prescriptions waiting" />
        </Card>
      ) : (
        <div className="space-y-4">
          {byPatient.map(([patientId, group]) => (
            <Card key={patientId} className="flex flex-wrap items-center gap-4 p-5">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900">{group.name}</p>
                <p className="text-sm text-slate-600">{group.items.map((item) => item.medication_name).join(', ')}</p>
                <p className="text-xs text-slate-500">
                  Dr {group.items[0].prescribed_by} · {formatDateTime(group.items[0].created_at)}
                </p>
              </div>
              <Button onClick={() => setDispensingFor(patientId)}>Dispense</Button>
            </Card>
          ))}
        </div>
      )}
      {active && <DispenseModal patientName={active[1].name} prescriptions={active[1].items} onClose={() => setDispensingFor(null)} />}
    </>
  )
}
