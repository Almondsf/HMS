import { UserPlus } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useRetrySignup, useSignups, type PlatformSignup, type SignupStatus } from '@/api/platform'
import { Badge, Button, Card, cx, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { formatDateTime, titleCase } from '@/lib/format'

const FILTERS: { value: SignupStatus | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Waiting for email' },
  { value: 'provisioning', label: 'Setting up' },
  { value: 'ready', label: 'Created' },
  { value: 'failed', label: 'Failed' },
]

const TONES = { pending: 'gray', provisioning: 'brand', ready: 'green', failed: 'red' } as const

const STALLED_AFTER_MS = 15 * 60_000

function isStuck(signup: PlatformSignup) {
  return (
    signup.status === 'provisioning' &&
    !!signup.provisioning_started_at &&
    Date.now() - new Date(signup.provisioning_started_at).getTime() > STALLED_AFTER_MS
  )
}

function RetryButton({ signup }: { signup: PlatformSignup }) {
  const retry = useRetrySignup()
  return (
    <div className="space-y-1">
      <Button size="sm" variant="secondary" loading={retry.isPending} onClick={() => retry.mutate(signup.id)}>
        Retry
      </Button>
      <ErrorAlert error={retry.error} />
    </div>
  )
}

export function SignupsPage() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') ?? '') as SignupStatus | ''
  const [search, setSearch] = useState('')
  const { data, isLoading, error } = useSignups({ status: status || undefined, search: search.trim() })
  const signups = data?.results ?? []

  return (
    <>
      <PageHeader title="Signups" description="Everyone who signed up, and whether their hospital was created" />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1">
          {FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              aria-pressed={status === filter.value}
              onClick={() => setParams(filter.value ? { status: filter.value } : {}, { replace: true })}
              className={cx(
                'rounded-lg px-3 py-1.5 text-sm font-medium',
                status === filter.value
                  ? 'bg-brand-500 text-white'
                  : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50',
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search name, address or email"
          aria-label="Search signups"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 lg:w-72"
        />
      </div>
      <ErrorAlert error={error} />
      <Card>
        {isLoading ? (
          <Spinner />
        ) : signups.length === 0 ? (
          <EmptyState icon={<UserPlus className="size-5" />} title="No signups here" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Signed up</th>
                  <th className="px-4 py-3 font-medium">Hospital</th>
                  <th className="px-4 py-3 font-medium">Contact</th>
                  <th className="px-4 py-3 font-medium">Plan</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 align-top">
                {signups.map((signup) => {
                  const stuck = isStuck(signup)
                  return (
                    <tr key={signup.id}>
                      <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                        {formatDateTime(signup.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        {signup.hospital ? (
                          <Link
                            to={`/operator/hospitals/${signup.hospital}`}
                            className="font-medium text-brand-700 hover:underline"
                          >
                            {signup.hospital_name}
                          </Link>
                        ) : (
                          <span className="font-medium text-slate-900">{signup.hospital_name}</span>
                        )}
                        <p className="text-xs text-slate-500">{signup.address}</p>
                      </td>
                      <td className="px-4 py-3">
                        {signup.first_name} {signup.last_name}
                        <p className="text-xs text-slate-500">
                          {signup.email}
                          {signup.phone && ` · ${signup.phone}`}
                        </p>
                      </td>
                      <td className="px-4 py-3">{titleCase(signup.plan)}</td>
                      <td className="px-4 py-3">
                        <Badge tone={stuck ? 'amber' : TONES[signup.status]}>
                          {stuck ? 'Stuck' : FILTERS.find((filter) => filter.value === signup.status)?.label}
                        </Badge>
                        {signup.error && <p className="mt-1 max-w-xs text-xs text-red-600">{signup.error}</p>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {(signup.status === 'failed' || stuck) && <RetryButton signup={signup} />}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
