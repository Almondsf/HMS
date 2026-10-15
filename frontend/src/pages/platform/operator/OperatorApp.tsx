/**
 * The platform operator's dashboard, at <platform>/operator. Only platform
 * superusers get in (the API checks this too).
 */
import { AlertTriangle, LogOut } from 'lucide-react'
import { Suspense, type ReactNode } from 'react'
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation } from 'react-router'

import { useOverview, type AttentionRow } from '@/api/platform'
import { BarList, StatTile } from '@/components/charts'
import { Button, Card, cx, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { AuthProvider, useAuth } from '@/lib/auth'
import { formatDate, titleCase } from '@/lib/format'
import { productName } from '@/lib/tenant'
import { LoginPage } from '@/pages/LoginPage'

import { HospitalDetailPage, HospitalsPage } from './HospitalPages'
import { naira, STATE_LABELS } from './shared'
import { ProvidersPage } from './ProvidersPage'
import { SignupsPage } from './SignupsPage'

function RequireOperator({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Restoring your session" />
  if (!user) return <Navigate to="/operator/login" replace state={{ from: location.pathname + location.search }} />
  if (!user.is_platform_operator) {
    return (
      <div className="mx-auto max-w-md px-4 py-16">
        <EmptyState title="This account can't open the operator dashboard">
          Only platform operators can. Hospital staff sign in at their hospital's own address.
          <div className="mt-4">
            <Button variant="secondary" onClick={() => void logout()}>
              Sign out
            </Button>
          </div>
        </EmptyState>
      </div>
    )
  }
  return children
}

const TABS = [
  { to: '/operator', label: 'Overview', end: true },
  { to: '/operator/hospitals', label: 'Hospitals', end: false },
  { to: '/operator/signups', label: 'Signups', end: false },
  { to: '/operator/providers', label: 'Providers', end: false },
]

function OperatorLayout() {
  const { user, logout } = useAuth()
  return (
    <div className="flex min-h-full flex-col bg-slate-50/60">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Link to="/operator" className="font-semibold text-slate-900">
            {productName()} <span className="font-normal text-brand-600">operator</span>
          </Link>
          <nav
            aria-label="Operator"
            className="order-last -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto"
          >
            {TABS.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cx(
                    'whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium',
                    isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-sm text-slate-600 sm:inline">{user?.email}</span>
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-lg p-2 text-slate-500 hover:bg-brand-50 hover:text-brand-700"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="size-5" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Suspense fallback={<Spinner />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}

function AttentionList({
  title,
  rows,
  date,
}: {
  title: string
  rows: AttentionRow[]
  date: (row: AttentionRow) => string
}) {
  return (
    <Card>
      <h3 className="border-b border-slate-100 px-5 py-3 font-medium text-slate-900">
        {title} <span className="text-slate-400">({rows.length})</span>
      </h3>
      {rows.length === 0 ? (
        <p className="px-5 py-4 text-sm text-slate-500">Nothing here.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {rows.map((row) => (
            <li key={row.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
              <div className="min-w-0">
                <Link to={`/operator/hospitals/${row.id}`} className="font-medium text-brand-700 hover:underline">
                  {row.name}
                </Link>
                <p className="truncate text-xs text-slate-500">
                  {titleCase(row.plan)} · {row.billing_email || row.domain}
                </p>
              </div>
              <span className="shrink-0 text-right text-slate-600">{date(row)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

const monthLabel = (month: string) =>
  new Date(`${month}-01T00:00:00`).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })

function OverviewPage() {
  const { data, isLoading, error } = useOverview()
  if (isLoading) return <Spinner />
  if (!data) return <ErrorAlert error={error} />

  const { hospitals, revenue, signups, attention } = data
  const signupsTotal = Object.values(signups.last_30_days).reduce((sum, count) => sum + (count ?? 0), 0)

  return (
    <>
      <PageHeader title="Overview" description="How the business is doing, and who needs attention" />
      {signups.stalled > 0 && (
        <div
          role="alert"
          className="mb-6 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
        >
          <AlertTriangle className="size-4 shrink-0" aria-hidden />
          {signups.stalled} hospital setup{signups.stalled === 1 ? ' is' : 's are'} stuck.{' '}
          <Link to="/operator/signups?status=provisioning" className="font-medium underline">
            Review
          </Link>
        </div>
      )}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Monthly recurring revenue"
          value={naira(revenue.monthly_recurring)}
          detail="Paying hospitals at today's prices (yearly ÷ 12)"
        />
        <StatTile label="Collected this month" value={naira(revenue.this_month)} />
        <StatTile
          label="Hospitals"
          value={hospitals.total}
          detail={`${hospitals.paying} paying · ${hospitals.trialing} on trial`}
        />
        <StatTile
          label="Signups, last 30 days"
          value={signupsTotal}
          detail={`${signups.last_30_days.ready ?? 0} created · ${signups.last_30_days.failed ?? 0} failed`}
        />
      </div>

      <h2 className="mb-3 font-medium text-slate-900">Needs attention</h2>
      <div className="mb-8 grid gap-4 lg:grid-cols-3">
        <AttentionList
          title="Trials ending this week"
          rows={attention.trials_ending}
          date={(row) => `ends ${formatDate(row.current_period_end)}`}
        />
        <AttentionList
          title="Overdue, in grace period"
          rows={attention.overdue}
          date={(row) => `read-only from ${formatDate(row.grace_ends_at)}`}
        />
        <AttentionList
          title="Lapsed (read-only)"
          rows={attention.lapsed}
          date={(row) => `since ${formatDate(row.grace_ends_at)}`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <BarList
          title="Collected per month"
          format={naira}
          empty="No payments yet."
          rows={revenue.by_month.map(({ month, total }) => ({
            key: month,
            label: monthLabel(month),
            value: Number(total),
          }))}
        />
        <BarList
          title="Hospitals by state"
          rows={(['paying', 'trialing', 'overdue', 'lapsed', 'suspended'] as const).map((state) => ({
            key: state,
            label: STATE_LABELS[state],
            value: hospitals[state],
          }))}
        />
      </div>
    </>
  )
}

export function OperatorApp() {
  return (
    <AuthProvider>
      <Routes>
        <Route
          path="login"
          element={<LoginPage home="/operator" title={`${productName()} operators`} allowReset={false} />}
        />
        <Route
          element={
            <RequireOperator>
              <OperatorLayout />
            </RequireOperator>
          }
        >
          <Route index element={<OverviewPage />} />
          <Route path="hospitals" element={<HospitalsPage />} />
          <Route path="hospitals/:id" element={<HospitalDetailPage />} />
          <Route path="signups" element={<SignupsPage />} />
          <Route path="providers" element={<ProvidersPage />} />
          <Route path="*" element={<Navigate to="/operator" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
