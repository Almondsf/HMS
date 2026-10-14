import { useState, type FormEvent } from 'react'

import { useSaveHospitalSettings } from '@/api/admin'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Spinner, Textarea } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useHospital, type Hospital } from '@/lib/hospital'
import { titleCase } from '@/lib/format'

function SettingsForm({ hospital }: { hospital: Hospital }) {
  const save = useSaveHospitalSettings()
  const [form, setForm] = useState({
    name: hospital.name,
    contact_email: hospital.contact_email,
    phone: hospital.phone,
    address: hospital.address,
    timezone: hospital.timezone,
    currency: hospital.currency,
    mrn_prefix: hospital.mrn_prefix,
  })
  const [saved, setSaved] = useState(false)
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {}
  const set = (field: keyof typeof form) => (event: { target: { value: string } }) => {
    setSaved(false)
    setForm({ ...form, [field]: event.target.value })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save.mutate(form, { onSuccess: () => setSaved(true) })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card className="space-y-4 p-5">
        <h2 className="font-medium text-slate-900">Hospital</h2>
        <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
        <Input label="Name" required value={form.name} onChange={set('name')} error={errors.name} hint="Shown on receipts, lab reports and claims" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Email" type="email" value={form.contact_email} onChange={set('contact_email')} error={errors.contact_email} />
          <Input label="Phone" value={form.phone} onChange={set('phone')} />
        </div>
        <Textarea label="Address" value={form.address} onChange={set('address')} />
      </Card>
      <Card className="space-y-4 p-5">
        <h2 className="font-medium text-slate-900">Regional</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Input label="Timezone" value={form.timezone} onChange={set('timezone')} error={errors.timezone} hint="e.g. Africa/Lagos" />
          <Input label="Currency" value={form.currency} onChange={set('currency')} error={errors.currency} hint="e.g. NGN, GHS, KES" />
          <Input label="Record number prefix" value={form.mrn_prefix} onChange={set('mrn_prefix')} error={errors.mrn_prefix} hint="New patients get PREFIX-000123" />
        </div>
      </Card>
      <div className="flex items-center justify-end gap-3">
        {saved && <span className="text-sm text-emerald-700">Saved</span>}
        <Button type="submit" loading={save.isPending}>
          Save settings
        </Button>
      </div>
    </form>
  )
}

export function SettingsPage() {
  const { data: hospital, isLoading, error } = useHospital()
  if (isLoading) return <Spinner />
  if (!hospital) return <ErrorAlert error={error} />
  return (
    <>
      <PageHeader title="Settings" description={hospital.domain ?? undefined} />
      <Card className="mb-6 flex flex-wrap items-center gap-3 p-5">
        <span className="text-sm text-slate-600">Plan</span>
        <Badge tone="brand">{titleCase(hospital.plan)}</Badge>
        <span className="text-sm text-slate-600">Modules:</span>
        {hospital.features.map((feature) => (
          <Badge key={feature}>{titleCase(feature)}</Badge>
        ))}
      </Card>
      <SettingsForm hospital={hospital} />
    </>
  )
}
