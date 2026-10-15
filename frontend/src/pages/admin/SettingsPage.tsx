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

function Toggle({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string
  hint: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className={`flex items-start gap-3 text-sm ${disabled ? 'opacity-60' : ''}`}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
      />
      <span>
        <span className="font-medium text-slate-900">{label}</span>
        <span className="block text-slate-500">{hint}</span>
      </span>
    </label>
  )
}

function SmsSettings({ hospital }: { hospital: Hospital }) {
  const save = useSaveHospitalSettings()
  const [form, setForm] = useState({
    sms_booking_confirmations: hospital.sms_booking_confirmations,
    sms_reminders: hospital.sms_reminders,
    sms_sender_id: hospital.sms_sender_id,
  })
  const [saved, setSaved] = useState(false)
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {}
  const update = (changes: Partial<typeof form>) => {
    setSaved(false)
    setForm({ ...form, ...changes })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    save.mutate(form, { onSuccess: () => setSaved(true) })
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6">
      <Card className="space-y-4 p-5">
        <div>
          <h2 className="font-medium text-slate-900">Patient SMS</h2>
          <p className="mt-1 text-sm text-slate-500">
            Fewer missed appointments. Patients without a mobile number, or who asked not to get SMS, are skipped.
          </p>
        </div>
        {!hospital.sms_available && (
          <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            SMS isn't available yet. The platform team is setting it up.
          </p>
        )}
        <Toggle
          label="Booking confirmations"
          hint="When an appointment is booked or moved"
          checked={form.sms_booking_confirmations}
          disabled={!hospital.sms_available}
          onChange={(checked) => update({ sms_booking_confirmations: checked })}
        />
        <Toggle
          label="Day-before reminders"
          hint="The morning before each appointment"
          checked={form.sms_reminders}
          disabled={!hospital.sms_available}
          onChange={(checked) => update({ sms_reminders: checked })}
        />
        <div className="max-w-xs">
          <Input
            label="Sender name (optional)"
            value={form.sms_sender_id}
            maxLength={11}
            disabled={!hospital.sms_available}
            onChange={(event) => update({ sms_sender_id: event.target.value })}
            error={errors.sms_sender_id}
            hint="What patients see as the sender, e.g. STLUKES. Ask the platform team to register it first."
          />
        </div>
        <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
        <div className="flex items-center justify-end gap-3">
          {saved && <span className="text-sm text-emerald-700">Saved</span>}
          <Button type="submit" variant="secondary" loading={save.isPending} disabled={!hospital.sms_available}>
            Save SMS settings
          </Button>
        </div>
      </Card>
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
      <SmsSettings hospital={hospital} />
    </>
  )
}
