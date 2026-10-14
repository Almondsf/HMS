import { Building2, Compass } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState } from '@/components/ui'

/** Opened at the bare platform address instead of a hospital's own. */
export function NoHospitalPage() {
  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-b from-brand-50 to-white px-4">
      <EmptyState icon={<Building2 className="size-6" />} title="Open your hospital's address">
        Each hospital has its own address, for example <span className="font-mono">yourhospital.hms.app</span>.
        Ask your administrator for yours.
      </EmptyState>
    </div>
  )
}

export function NotFoundPage() {
  return (
    <EmptyState icon={<Compass className="size-6" />} title="Page not found">
      <Link to="/" className="font-medium text-brand-600 hover:text-brand-700">
        Back to the dashboard
      </Link>
    </EmptyState>
  )
}
