import { Compass } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState } from '@/components/ui'

export function NotFoundPage() {
  return (
    <EmptyState icon={<Compass className="size-6" />} title="Page not found">
      <Link to="/" className="font-medium text-brand-600 hover:text-brand-700">
        Back to the dashboard
      </Link>
    </EmptyState>
  )
}
