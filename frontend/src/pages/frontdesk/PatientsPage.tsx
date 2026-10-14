import { UserPlus, Users } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { fullName, usePatients, useSavePatient } from '@/api/frontDesk'
import { PatientForm, SearchBox, useDebounced } from '@/components/frontDesk'
import { Modal } from '@/components/Modal'
import { Button, Card, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { age } from '@/lib/format'

export function PatientsPage() {
  const user = useCurrentUser()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [registering, setRegistering] = useState(false)
  const debounced = useDebounced(search)
  const { data, isLoading, error } = usePatients(debounced, page)
  const save = useSavePatient()
  const canRegister = user.user_type === 'receptionist' || user.user_type === 'admin'

  return (
    <>
      <PageHeader
        title="Patients"
        description="Search by name, record number (MRN) or phone."
        actions={
          canRegister && (
            <Button icon={<UserPlus className="size-4" />} onClick={() => setRegistering(true)}>
              Register patient
            </Button>
          )
        }
      />

      <Card>
        <div className="border-b border-slate-200 p-4">
          <SearchBox
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            placeholder="Search patients"
          />
        </div>
        <ErrorAlert error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data?.results.length ? (
          <EmptyState icon={<Users className="size-6" />} title={debounced ? 'No matching patients' : 'No patients yet'}>
            {canRegister && 'Register the first patient to get started.'}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">MRN</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Age / sex</th>
                  <th className="px-4 py-3">Phone</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((patient) => (
                  <tr key={patient.id} className="hover:bg-brand-50/50">
                    <td className="px-4 py-3 font-mono text-xs text-slate-600">{patient.mrn}</td>
                    <td className="px-4 py-3">
                      <Link to={`/patients/${patient.id}`} className="font-medium text-brand-700 hover:underline">
                        {fullName(patient.user)}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {[age(patient.user.date_of_birth), patient.user.gender?.charAt(0).toUpperCase()]
                        .filter((part) => part !== null && part !== undefined)
                        .join(' / ') || '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{patient.user.phone_number ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && (data.next || data.previous) && (
          <div className="flex items-center justify-between border-t border-slate-200 p-4 text-sm text-slate-600">
            <span>{data.count} patients</span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={!data.previous} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <Button variant="secondary" size="sm" disabled={!data.next} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Modal open={registering} title="Register patient" onClose={() => setRegistering(false)} wide>
        <PatientForm
          submitLabel="Register"
          submitting={save.isPending}
          error={save.error}
          onSubmit={(input) =>
            save.mutate(input, {
              onSuccess: (patient) => {
                setRegistering(false)
                navigate(`/patients/${patient.id}`)
              },
            })
          }
        />
      </Modal>
    </>
  )
}
