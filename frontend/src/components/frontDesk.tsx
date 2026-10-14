import { Search } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'

import { fullName, useDoctors, usePatients, type Patient, type PatientInput } from '@/api/frontDesk'
import { Button, ErrorAlert, Input, Select, Textarea, cx } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { age } from '@/lib/format'

/** Debounce a fast-changing value (search boxes). */
export function useDebounced<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export function patientSummary(patient: Patient): string {
  const years = age(patient.user.date_of_birth)
  return [patient.mrn, years !== null ? `${years}y` : null, patient.user.gender, patient.user.phone_number]
    .filter(Boolean)
    .join(' · ')
}

/** Search patients by name, MRN or phone and pick one. */
export function PatientPicker({
  value,
  onChange,
  error,
}: {
  value: Patient | null
  onChange: (patient: Patient | null) => void
  error?: string
}) {
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search)
  const { data, isFetching } = usePatients(debounced)

  if (value) {
    return (
      <div className="space-y-1.5">
        <p className="text-sm font-medium text-slate-700">Patient</p>
        <div className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50 px-3 py-2">
          <div>
            <p className="text-sm font-medium text-slate-900">{fullName(value.user)}</p>
            <p className="text-xs text-slate-500">{patientSummary(value)}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => onChange(null)}>
            Change
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <Input
        label="Patient"
        placeholder="Name, MRN or phone"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        error={error}
        autoFocus
      />
      {debounced && (
        <ul className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
          {data?.results.map((patient) => (
            <li key={patient.id}>
              <button
                type="button"
                onClick={() => onChange(patient)}
                className="w-full px-3 py-2 text-left hover:bg-brand-50"
              >
                <p className="text-sm font-medium text-slate-900">{fullName(patient.user)}</p>
                <p className="text-xs text-slate-500">{patientSummary(patient)}</p>
              </button>
            </li>
          ))}
          {!isFetching && data?.results.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500">No patients match “{debounced}”.</li>
          )}
        </ul>
      )}
    </div>
  )
}

export function DoctorSelect({
  value,
  onChange,
  error,
  label = 'Doctor',
  allowAll = false,
}: {
  value: number | ''
  onChange: (doctorId: number | '') => void
  error?: string
  label?: string
  allowAll?: boolean
}) {
  const { data: doctors } = useDoctors()
  return (
    <Select
      label={label}
      value={value}
      error={error}
      onChange={(event) => onChange(event.target.value ? Number(event.target.value) : '')}
    >
      <option value="">{allowAll ? 'All doctors' : 'Choose a doctor'}</option>
      {doctors
        ?.filter((doctor) => doctor.doctor_id !== null)
        .map((doctor) => (
          <option key={doctor.id} value={doctor.doctor_id!}>
            Dr {doctor.full_name}
            {doctor.specialty ? ` · ${doctor.specialty}` : ''}
          </option>
        ))}
    </Select>
  )
}

/** Register or edit a patient. */
export function PatientForm({
  initial,
  onSubmit,
  submitting,
  error,
  submitLabel,
}: {
  initial?: Patient
  onSubmit: (input: PatientInput) => void
  submitting: boolean
  error: unknown
  submitLabel: string
}) {
  const [form, setForm] = useState({
    mrn: initial?.mrn ?? '',
    first_name: initial?.user.first_name ?? '',
    last_name: initial?.user.last_name ?? '',
    gender: initial?.user.gender ?? '',
    date_of_birth: initial?.user.date_of_birth ?? '',
    phone_number: initial?.user.phone_number ?? '',
    email: initial?.user.email ?? '',
    address: initial?.user.address ?? '',
    emergency_contact: initial?.user.emergency_contact ?? '',
    emergency_phone: initial?.user.emergency_phone ?? '',
    blood_group: initial?.blood_group ?? '',
    genotype: initial?.genotype ?? '',
    allergies: initial?.allergies ?? '',
  })
  const set = (field: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }))

  const fieldErrors = error instanceof ApiError ? error.fieldErrors : {}
  const userErrors =
    error instanceof ApiError && error.data && typeof error.data === 'object' && 'user' in error.data
      ? new ApiError(400, (error.data as { user: unknown }).user).fieldErrors
      : {}

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    onSubmit({
      ...(initial ? {} : form.mrn ? { mrn: form.mrn } : {}),
      user: {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        gender: (form.gender || null) as PatientInput['user']['gender'],
        date_of_birth: form.date_of_birth || null,
        phone_number: form.phone_number || null,
        email: form.email || null,
        address: form.address || null,
        emergency_contact: form.emergency_contact || null,
        emergency_phone: form.emergency_phone || null,
      },
      blood_group: form.blood_group || null,
      genotype: form.genotype || null,
      allergies: form.allergies,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <ErrorAlert error={Object.keys({ ...fieldErrors, ...userErrors }).length ? null : error} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="First name" required value={form.first_name} onChange={set('first_name')} error={userErrors.first_name} />
        <Input label="Last name" required value={form.last_name} onChange={set('last_name')} error={userErrors.last_name} />
        <Select label="Gender" value={form.gender} onChange={set('gender')}>
          <option value="">Not recorded</option>
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="other">Other</option>
        </Select>
        <Input label="Date of birth" type="date" value={form.date_of_birth} onChange={set('date_of_birth')} error={userErrors.date_of_birth} />
        <Input label="Phone" type="tel" value={form.phone_number} onChange={set('phone_number')} error={userErrors.phone_number} hint="e.g. +2348012345678" />
        <Input label="Email" type="email" value={form.email} onChange={set('email')} error={userErrors.email} hint="Optional" />
      </div>
      <Textarea label="Address" rows={2} value={form.address} onChange={set('address')} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Emergency contact" value={form.emergency_contact} onChange={set('emergency_contact')} />
        <Input label="Emergency phone" type="tel" value={form.emergency_phone} onChange={set('emergency_phone')} error={userErrors.emergency_phone} />
        <Select label="Blood group" value={form.blood_group} onChange={set('blood_group')}>
          <option value="">Unknown</option>
          {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map((group) => (
            <option key={group}>{group}</option>
          ))}
        </Select>
        <Select label="Genotype" value={form.genotype} onChange={set('genotype')}>
          <option value="">Unknown</option>
          {['AA', 'AS', 'SS', 'AC', 'SC'].map((genotype) => (
            <option key={genotype}>{genotype}</option>
          ))}
        </Select>
      </div>
      <Textarea label="Allergies" rows={2} value={form.allergies} onChange={set('allergies')} />
      {!initial && (
        <Input
          label="Existing record number"
          value={form.mrn}
          onChange={set('mrn')}
          error={fieldErrors.mrn}
          hint="Only for patients with a paper record number to keep. Leave blank to assign one."
        />
      )}
      <div className="flex justify-end">
        <Button type="submit" loading={submitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}

export function StatusDot({ tone }: { tone: 'green' | 'amber' | 'red' | 'gray' | 'brand' }) {
  const colours = {
    green: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
    gray: 'bg-slate-400',
    brand: 'bg-brand-500',
  }
  return <span className={cx('inline-block size-2 rounded-full', colours[tone])} aria-hidden />
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
      />
    </div>
  )
}
