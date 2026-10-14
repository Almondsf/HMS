import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useDrugs, useSaveDrug, type DrugItem } from '@/api/labPharmacy'
import { SearchBox, useDebounced } from '@/components/frontDesk'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatMoney, useHospital } from '@/lib/hospital'

function DrugModal({ drug, onClose }: { drug?: DrugItem; onClose: () => void }) {
  const save = useSaveDrug()
  const [form, setForm] = useState({
    name: drug?.name ?? '',
    unit: drug?.unit ?? 'tablet',
    quantity_in_stock: String(drug?.quantity_in_stock ?? 0),
    reorder_level: String(drug?.reorder_level ?? 0),
    unit_price: drug?.unit_price ?? '',
  })
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {}
  const set = (field: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save.mutate(
      {
        id: drug?.id,
        name: form.name,
        unit: form.unit,
        quantity_in_stock: Number(form.quantity_in_stock),
        reorder_level: Number(form.reorder_level),
        unit_price: form.unit_price === '' ? null : form.unit_price,
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal open title={drug ? `Edit ${drug.name}` : 'Add drug'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
        <Input label="Name" required value={form.name} onChange={set('name')} error={errors.name} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Unit" required value={form.unit} onChange={set('unit')} hint="tablet, ml, vial…" />
          <Input label="Price per unit" type="number" min={0} step="0.01" value={form.unit_price} onChange={set('unit_price')} error={errors.unit_price} hint="Charged when dispensed" />
          <Input label="In stock" type="number" min={0} required value={form.quantity_in_stock} onChange={set('quantity_in_stock')} error={errors.quantity_in_stock} />
          <Input label="Reorder at" type="number" min={0} required value={form.reorder_level} onChange={set('reorder_level')} />
        </div>
        <div className="flex justify-end">
          <Button type="submit" loading={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function DrugsPage() {
  const [search, setSearch] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const debounced = useDebounced(search)
  const { data: drugs, isLoading, error } = useDrugs({ name: debounced, low_stock: lowOnly })
  const { data: hospital } = useHospital()
  const [editing, setEditing] = useState<DrugItem | 'new' | null>(null)

  return (
    <>
      <PageHeader
        title="Drugs & stock"
        actions={
          <Button icon={<Plus className="size-4" />} onClick={() => setEditing('new')}>
            Add drug
          </Button>
        }
      />
      <Card>
        <div className="flex flex-wrap items-center gap-4 border-b border-slate-200 p-4">
          <div className="min-w-60 flex-1">
            <SearchBox value={search} onChange={setSearch} placeholder="Search drugs" />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="accent-brand-500" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} />
            Low stock only
          </label>
        </div>
        <ErrorAlert error={error} />
        {isLoading ? (
          <Spinner />
        ) : (
          <ul className="divide-y divide-slate-100">
            {drugs?.map((drug) => (
              <li key={drug.id}>
                <button type="button" onClick={() => setEditing(drug)} className="flex w-full flex-wrap items-center gap-4 px-5 py-3 text-left hover:bg-brand-50/50">
                  <span className="flex-1 text-sm font-medium text-slate-900">{drug.name}</span>
                  {drug.is_low_stock && <Badge tone="amber">Low stock</Badge>}
                  {drug.unit_price === null && <Badge tone="red">No price</Badge>}
                  <span className="w-32 text-right text-sm text-slate-700">
                    {drug.quantity_in_stock} {drug.unit}
                  </span>
                  <span className="w-28 text-right text-sm text-slate-900">
                    {drug.unit_price !== null ? formatMoney(drug.unit_price, hospital?.currency) : '—'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {editing && <DrugModal drug={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
    </>
  )
}
