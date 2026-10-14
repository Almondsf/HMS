import { UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { STAFF_ENDPOINTS, useCreateStaff, useDepartments, useSetStaffActive, useStaff, type StaffRole } from '@/api/admin'
import { SearchBox, useDebounced } from '@/components/frontDesk'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useCurrentUser } from '@/lib/auth'
import { ROLE_LABELS, type Role } from '@/lib/roles'

const STAFF_ROLES = Object.keys(STAFF_ENDPOINTS) as StaffRole[]

function AddStaffModal({ onClose }: { onClose: () => void }) {
  const create = useCreateStaff()
  const { data: departments } = useDepartments()
  const [role, setRole] = useState<StaffRole>('doctor')
  const [user, setUser] = useState({ first_name: '', last_name: '', email: '', phone_number: '', password: '' })
  const [profile, setProfile] = useState({ specialty: '', license_number: '', department: '' })

  const data = create.error instanceof ApiError ? (create.error.data as Record<string, unknown> | null) : null
  const userErrors = data && typeof data.user === 'object' ? new ApiError(400, data.user).fieldErrors : {}
  const errors = create.error instanceof ApiError ? create.error.fieldErrors : {}
  const setUserField = (field: keyof typeof user) => (event: { target: { value: string } }) => setUser({ ...user, [field]: event.target.value })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const extra: Record<string, unknown> = {}
    if (role === 'doctor') extra.specialty = profile.specialty
    if (role === 'doctor' || role === 'nurse') {
      extra.license_number = profile.license_number || null
      extra.department = profile.department ? Number(profile.department) : null
    }
    create.mutate({ role, user: { ...user, phone_number: user.phone_number || null }, ...extra }, { onSuccess: onClose })
  }

  return (
    <Modal open title="Add staff member" onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={Object.keys({ ...errors, ...userErrors }).length ? null : create.error} />
        <Select label="Role" value={role} onChange={(event) => setRole(event.target.value as StaffRole)}>
          {STAFF_ROLES.map((option) => (
            <option key={option} value={option}>
              {ROLE_LABELS[option]}
            </option>
          ))}
        </Select>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="First name" required value={user.first_name} onChange={setUserField('first_name')} error={userErrors.first_name} />
          <Input label="Last name" required value={user.last_name} onChange={setUserField('last_name')} error={userErrors.last_name} />
          <Input label="Email" type="email" required value={user.email} onChange={setUserField('email')} error={userErrors.email} hint="They sign in with this" />
          <Input label="Phone" type="tel" value={user.phone_number} onChange={setUserField('phone_number')} error={userErrors.phone_number} />
        </div>
        <Input
          label="Temporary password"
          type="password"
          autoComplete="new-password"
          required
          value={user.password}
          onChange={setUserField('password')}
          error={userErrors.password}
          hint="At least 10 characters. Ask them to change it after their first sign-in."
        />
        {(role === 'doctor' || role === 'nurse') && (
          <div className="grid gap-4 sm:grid-cols-2">
            {role === 'doctor' && (
              <Input label="Specialty" required value={profile.specialty} onChange={(e) => setProfile({ ...profile, specialty: e.target.value })} error={errors.specialty} />
            )}
            <Input label="Licence number" value={profile.license_number} onChange={(e) => setProfile({ ...profile, license_number: e.target.value })} error={errors.license_number} />
            <Select label="Department" value={profile.department} onChange={(e) => setProfile({ ...profile, department: e.target.value })}>
              <option value="">None</option>
              {departments
                ?.filter((department) => department.is_active)
                .map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
            </Select>
          </div>
        )}
        <div className="flex justify-end">
          <Button type="submit" loading={create.isPending}>
            Create account
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function StaffPage() {
  const me = useCurrentUser()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [adding, setAdding] = useState(false)
  const debounced = useDebounced(search)
  const { data: staff, isLoading, error } = useStaff({ role: role || undefined, search: debounced, is_active: showInactive ? undefined : true })
  const setActive = useSetStaffActive()

  return (
    <>
      <PageHeader
        title="Staff"
        actions={
          <Button icon={<UserPlus className="size-4" />} onClick={() => setAdding(true)}>
            Add staff
          </Button>
        }
      />
      <ErrorAlert error={setActive.error} />
      <Card>
        <div className="flex flex-wrap items-end gap-4 border-b border-slate-200 p-4">
          <div className="min-w-60 flex-1">
            <SearchBox value={search} onChange={setSearch} placeholder="Search staff" />
          </div>
          <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
            <option value="">All roles</option>
            {[...STAFF_ROLES, 'admin'].map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option as Role]}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="accent-brand-500" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
            Include deactivated
          </label>
        </div>
        <ErrorAlert error={error} />
        {isLoading ? (
          <Spinner />
        ) : (
          <ul className="divide-y divide-slate-100">
            {staff?.map((member) => (
              <li key={member.id} className="flex flex-wrap items-center gap-4 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">{member.full_name}</p>
                  <p className="text-xs text-slate-500">
                    {member.email}
                    {member.specialty ? ` · ${member.specialty}` : ''}
                    {member.department ? ` · ${member.department.name}` : ''}
                  </p>
                </div>
                <Badge tone="brand">{ROLE_LABELS[member.role as Role] ?? member.role}</Badge>
                {!member.is_active && <Badge tone="red">Deactivated</Badge>}
                {member.id !== me.id &&
                  (member.is_active ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        window.confirm(`Deactivate ${member.full_name}? They will be signed out everywhere.`) &&
                        setActive.mutate({ id: member.id, active: false })
                      }
                    >
                      Deactivate
                    </Button>
                  ) : (
                    <Button size="sm" variant="secondary" onClick={() => setActive.mutate({ id: member.id, active: true })}>
                      Reactivate
                    </Button>
                  ))}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {adding && <AddStaffModal onClose={() => setAdding(false)} />}
    </>
  )
}
