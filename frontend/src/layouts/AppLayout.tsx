import { KeyRound, LogOut, Menu, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'

import { cx } from '@/components/ui'
import { useCurrentUser, useAuth } from '@/lib/auth'
import { useHospital } from '@/lib/hospital'
import { visibleNavItems } from '@/lib/navigation'
import { ROLE_LABELS } from '@/lib/roles'

function Logo({ name }: { name?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-9 place-items-center rounded-lg bg-brand-500 text-white" aria-hidden>
        <svg viewBox="0 0 24 24" className="size-5" fill="currentColor">
          <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" />
        </svg>
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-slate-900">{name ?? 'HMS'}</p>
        <p className="text-xs text-brand-600">Hospital Management</p>
      </div>
    </div>
  )
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const user = useCurrentUser()
  const { data: hospital } = useHospital()
  const items = visibleNavItems(user.user_type, hospital?.features ?? [])

  return (
    <nav aria-label="Main" className="flex h-full flex-col gap-6 p-4">
      <Logo name={hospital?.name} />
      <ul className="space-y-1">
        {items.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                cx(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                )
              }
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export function AppLayout() {
  const user = useCurrentUser()
  const { logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex h-full bg-slate-50/60">
      {/* Desktop sidebar */}
      <aside className="no-print hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block">
        <Sidebar />
      </aside>

      {/* Mobile sidebar */}
      {menuOpen && (
        <div className="no-print fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/30" onClick={() => setMenuOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 w-72 bg-white shadow-xl">
            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              className="absolute right-3 top-3 rounded-lg p-2 text-slate-500 hover:bg-slate-100"
              aria-label="Close menu"
            >
              <X className="size-5" />
            </button>
            <Sidebar onNavigate={() => setMenuOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 sm:px-6">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </button>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium text-slate-900">{user.full_name}</p>
              <p className="text-xs text-brand-600">{ROLE_LABELS[user.user_type]}</p>
            </div>
            <NavLink
              to="/change-password"
              className="rounded-lg p-2 text-slate-500 hover:bg-brand-50 hover:text-brand-700"
              aria-label="Change password"
              title="Change password"
            >
              <KeyRound className="size-5" />
            </NavLink>
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
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
