import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useLabTests, useSaveLabTest, type LabTestItem } from '@/api/labPharmacy'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatMoney, useHospital } from '@/lib/hospital'

function TestModal({ test, onClose }: { test?: LabTestItem; onClose: () => void }) {
  const save = useSaveLabTest()
  const [form, setForm] = useState({
    name: test?.name ?? '',
    normal_range: test?.normal_range ?? '',
    cost: test?.cost ?? '',
    is_active: test?.is_active ?? true,
  })
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {}

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save.mutate({ id: test?.id, ...form }, { onSuccess: onClose })
  }

  return (
    <Modal open title={test ? `Edit ${test.name}` : 'Add test'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
        <Input label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={errors.name} />
        <Input label="Normal range" value={form.normal_range} onChange={(e) => setForm({ ...form, normal_range: e.target.value })} />
        <Input label="Price" type="number" min={0} step="0.01" required value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} error={errors.cost} />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="accent-brand-500" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
          Offered (untick to retire the test)
        </label>
        <div className="flex justify-end">
          <Button type="submit" loading={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function LabCataloguePage() {
  const { data: tests, isLoading, error } = useLabTests()
  const { data: hospital } = useHospital()
  const [editing, setEditing] = useState<LabTestItem | 'new' | null>(null)

  return (
    <>
      <PageHeader
        title="Lab tests & prices"
        actions={
          <Button icon={<Plus className="size-4" />} onClick={() => setEditing('new')}>
            Add test
          </Button>
        }
      />
      <ErrorAlert error={error} />
      <Card>
        {isLoading ? (
          <Spinner />
        ) : (
          <ul className="divide-y divide-slate-100">
            {tests?.map((test) => (
              <li key={test.id}>
                <button type="button" onClick={() => setEditing(test)} className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-brand-50/50">
                  <span className="flex-1 text-sm font-medium text-slate-900">{test.name}</span>
                  <span className="text-xs text-slate-500">{test.normal_range}</span>
                  {!test.is_active && <Badge>Retired</Badge>}
                  <span className="w-28 text-right text-sm text-slate-900">{formatMoney(test.cost, hospital?.currency)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {editing && <TestModal test={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
    </>
  )
}
