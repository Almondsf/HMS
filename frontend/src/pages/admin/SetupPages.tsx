/** Admin set-up lists: departments, the tariff (fees) and insurers. */
import { Plus } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import { useDepartments, useSaveDepartment, type Department } from '@/api/admin'
import { useProviders, useSaveProvider, useSaveServiceItem, useServiceItems, type Provider, type ServiceItem } from '@/api/billing'
import { Modal } from '@/components/Modal'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { titleCase } from '@/lib/format'
import { formatMoney, useHospital } from '@/lib/hospital'

function ListPage<T extends { id: number }>({
  title,
  description,
  addLabel,
  items,
  loading,
  error,
  row,
  editor,
}: {
  title: string
  description?: string
  addLabel: string
  items: T[] | undefined
  loading: boolean
  error: unknown
  row: (item: T) => ReactNode
  editor: (item: T | undefined, close: () => void) => ReactNode
}) {
  const [editing, setEditing] = useState<T | 'new' | null>(null)
  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={
          <Button icon={<Plus className="size-4" />} onClick={() => setEditing('new')}>
            {addLabel}
          </Button>
        }
      />
      <ErrorAlert error={error} />
      <Card>
        {loading ? (
          <Spinner />
        ) : !items?.length ? (
          <p className="p-5 text-sm text-slate-500">Nothing set up yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((item) => (
              <li key={item.id}>
                <button type="button" onClick={() => setEditing(item)} className="flex w-full flex-wrap items-center gap-4 px-5 py-3 text-left hover:bg-brand-50/50">
                  {row(item)}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {editing && editor(editing === 'new' ? undefined : editing, () => setEditing(null))}
    </>
  )
}

function useErrors(error: unknown) {
  return error instanceof ApiError ? error.fieldErrors : {}
}

// ---- Departments ----

function DepartmentModal({ department, onClose }: { department?: Department; onClose: () => void }) {
  const save = useSaveDepartment()
  const [form, setForm] = useState({ name: department?.name ?? '', description: department?.description ?? '', is_active: department?.is_active ?? true })
  const errors = useErrors(save.error)
  return (
    <Modal open title={department ? `Edit ${department.name}` : 'Add department'} onClose={onClose}>
      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          save.mutate({ id: department?.id, ...form }, { onSuccess: onClose })
        }}
        className="space-y-4"
      >
        <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
        <Input label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={errors.name} />
        <Input label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="accent-brand-500" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
          Active
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

export function DepartmentsPage() {
  const { data, isLoading, error } = useDepartments()
  return (
    <ListPage
      title="Departments"
      addLabel="Add department"
      items={data}
      loading={isLoading}
      error={error}
      row={(department) => (
        <>
          <span className="flex-1 text-sm font-medium text-slate-900">{department.name}</span>
          <span className="text-sm text-slate-500">{department.description}</span>
          {!department.is_active && <Badge>Inactive</Badge>}
        </>
      )}
      editor={(department, close) => <DepartmentModal department={department} onClose={close} />}
    />
  )
}

// ---- Tariff ----

const CATEGORIES = ['registration', 'consultation', 'procedure', 'lab', 'pharmacy', 'other']
const CHARGE_ON: Record<ServiceItem['charge_on'], string> = {
  manual: 'Added by the cashier',
  visit_opened: 'Automatically, every visit',
  consultation_recorded: 'Automatically, every consultation',
}

function ServiceItemModal({ item, onClose }: { item?: ServiceItem; onClose: () => void }) {
  const save = useSaveServiceItem()
  const [form, setForm] = useState({
    code: item?.code ?? '',
    name: item?.name ?? '',
    category: item?.category ?? 'consultation',
    price: item?.price ?? '',
    charge_on: item?.charge_on ?? ('manual' as ServiceItem['charge_on']),
    is_active: item?.is_active ?? true,
  })
  const errors = useErrors(save.error)
  return (
    <Modal open title={item ? `Edit ${item.name}` : 'Add fee'} onClose={onClose}>
      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          save.mutate({ id: item?.id, ...form }, { onSuccess: onClose })
        }}
        className="space-y-4"
      >
        <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={errors.name} />
          <Input label="Code" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} error={errors.code} hint="Short and unique, e.g. CONSULT" />
          <Select label="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {titleCase(category)}
              </option>
            ))}
          </Select>
          <Input label="Price" type="number" min={0} step="0.01" required value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} error={errors.price} />
        </div>
        <Select label="Charged" value={form.charge_on} onChange={(e) => setForm({ ...form, charge_on: e.target.value as ServiceItem['charge_on'] })}>
          {Object.entries(CHARGE_ON).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="accent-brand-500" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
          In use
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

export function TariffPage() {
  const { data, isLoading, error } = useServiceItems()
  const { data: hospital } = useHospital()
  return (
    <ListPage
      title="Fees"
      description="Consultation, card and procedure fees. Lab tests and drugs are priced on their own lists."
      addLabel="Add fee"
      items={data}
      loading={isLoading}
      error={error}
      row={(item) => (
        <>
          <span className="w-24 font-mono text-xs text-slate-500">{item.code}</span>
          <span className="flex-1 text-sm font-medium text-slate-900">{item.name}</span>
          {item.charge_on !== 'manual' && <Badge tone="brand">Automatic</Badge>}
          {!item.is_active && <Badge>Not in use</Badge>}
          <span className="w-28 text-right text-sm text-slate-900">{formatMoney(item.price, hospital?.currency)}</span>
        </>
      )}
      editor={(item, close) => <ServiceItemModal item={item} onClose={close} />}
    />
  )
}

// ---- Insurers ----

function ProviderModal({ provider, onClose }: { provider?: Provider; onClose: () => void }) {
  const save = useSaveProvider()
  const [form, setForm] = useState({
    name: provider?.name ?? '',
    code: provider?.code ?? '',
    kind: provider?.kind ?? 'hmo',
    default_coverage_percent: provider?.default_coverage_percent ?? '100',
    requires_authorization: provider?.requires_authorization ?? false,
    is_active: provider?.is_active ?? true,
  })
  const errors = useErrors(save.error)
  return (
    <Modal open title={provider ? `Edit ${provider.name}` : 'Add insurer'} onClose={onClose}>
      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          save.mutate({ id: provider?.id, ...form }, { onSuccess: onClose })
        }}
        className="space-y-4"
      >
        <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} error={errors.name} />
          <Input label="Code" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} error={errors.code} />
          <Select label="Type" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            <option value="hmo">HMO</option>
            <option value="nhia">NHIA (national scheme)</option>
            <option value="private">Private insurer</option>
            <option value="corporate">Corporate retainer</option>
          </Select>
          <Input label="Default coverage %" type="number" min={0} max={100} step="0.01" required value={form.default_coverage_percent} onChange={(e) => setForm({ ...form, default_coverage_percent: e.target.value })} />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="accent-brand-500" checked={form.requires_authorization} onChange={(e) => setForm({ ...form, requires_authorization: e.target.checked })} />
          Claims need a pre-authorisation code
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="accent-brand-500" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
          Accepted
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

export function InsurersPage() {
  const { data, isLoading, error } = useProviders()
  return (
    <ListPage
      title="Insurers & HMOs"
      addLabel="Add insurer"
      items={data}
      loading={isLoading}
      error={error}
      row={(provider) => (
        <>
          <span className="flex-1 text-sm font-medium text-slate-900">{provider.name}</span>
          <Badge tone="brand">{provider.kind.toUpperCase()}</Badge>
          {provider.requires_authorization && <Badge tone="amber">Pre-auth</Badge>}
          {!provider.is_active && <Badge>Not accepted</Badge>}
          <span className="w-24 text-right text-sm text-slate-700">{Number(provider.default_coverage_percent)}%</span>
        </>
      )}
      editor={(provider, close) => <ProviderModal provider={provider} onClose={close} />}
    />
  )
}
