import { Plus, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useAddCoverage, useCoverages, useProviders } from '@/api/billing'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, Select } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatDate, todayIso } from '@/lib/format'

function AddCoverModal({ patientId, onClose }: { patientId: number; onClose: () => void }) {
  const add = useAddCoverage(patientId)
  const { data: providers } = useProviders()
  const [form, setForm] = useState({
    provider: '',
    member_number: '',
    plan_name: '',
    coverage_percent: '',
    valid_from: todayIso(),
    valid_to: '',
  })
  const errors = add.error instanceof ApiError ? add.error.fieldErrors : {}
  const set = (field: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    add.mutate(
      {
        provider: Number(form.provider),
        member_number: form.member_number.trim(),
        plan_name: form.plan_name,
        coverage_percent: form.coverage_percent || null,
        valid_from: form.valid_from,
        valid_to: form.valid_to || null,
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal open title="Add insurance cover" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={Object.keys(errors).length ? null : add.error} />
        <Select label="Insurer / HMO" required value={form.provider} onChange={set('provider')} error={errors.provider}>
          <option value="">Choose</option>
          {providers
            ?.filter((provider) => provider.is_active)
            .map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
        </Select>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Member number" required value={form.member_number} onChange={set('member_number')} error={errors.member_number ?? errors.non_field_errors} />
          <Input label="Plan" value={form.plan_name} onChange={set('plan_name')} />
          <Input label="Valid from" type="date" required value={form.valid_from} onChange={set('valid_from')} />
          <Input label="Valid until" type="date" value={form.valid_to} onChange={set('valid_to')} error={errors.valid_to} hint="Blank: no end date" />
        </div>
        <Input label="Coverage %" type="number" min={0} max={100} step="0.01" value={form.coverage_percent} onChange={set('coverage_percent')} hint="Blank: the insurer's default" />
        <div className="flex justify-end">
          <Button type="submit" loading={add.isPending} disabled={!form.provider}>
            Add cover
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function InsuranceCover({ patientId, canEdit }: { patientId: number; canEdit: boolean }) {
  const { data: coverages, isLoading } = useCoverages(patientId, true)
  const [adding, setAdding] = useState(false)
  const today = todayIso()

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-medium text-slate-900">
          <ShieldCheck className="size-4 text-brand-600" aria-hidden /> Insurance
        </h2>
        {canEdit && (
          <Button size="sm" variant="ghost" icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>
            Add
          </Button>
        )}
      </div>
      {isLoading ? null : !coverages?.length ? (
        <p className="text-sm text-slate-500">No cover recorded. The patient pays directly.</p>
      ) : (
        <ul className="space-y-3">
          {coverages.map((cover) => {
            const current = cover.is_active && cover.valid_from <= today && (!cover.valid_to || cover.valid_to >= today)
            return (
              <li key={cover.id} className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-900">{cover.provider_name}</span>
                  <Badge tone={current ? 'green' : 'gray'}>{current ? `${Number(cover.effective_percent)}% covered` : 'Not current'}</Badge>
                </div>
                <p className="text-xs text-slate-500">
                  #{cover.member_number}
                  {cover.plan_name ? ` · ${cover.plan_name}` : ''} · from {formatDate(cover.valid_from)}
                  {cover.valid_to ? ` to ${formatDate(cover.valid_to)}` : ''}
                </p>
              </li>
            )
          })}
        </ul>
      )}
      {adding && <AddCoverModal patientId={patientId} onClose={() => setAdding(false)} />}
    </Card>
  )
}
