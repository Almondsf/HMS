import { RefreshCw, TriangleAlert } from 'lucide-react'

import { Button } from '@/components/ui'

/** Shown when the app hits an unexpected error, instead of a blank page. */
export function CrashScreen({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-b from-brand-50 to-white px-4">
      <div className="max-w-sm text-center">
        <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-amber-50 text-amber-600">
          <TriangleAlert className="size-6" aria-hidden />
        </div>
        <h1 className="text-lg font-semibold text-slate-900">Something went wrong</h1>
        <p className="mt-2 text-sm text-slate-600">
          The problem has been reported. Your saved work is safe: try again, or reload the page.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="secondary" onClick={() => window.location.reload()}>
            Reload page
          </Button>
          <Button icon={<RefreshCw className="size-4" />} onClick={onRetry}>
            Try again
          </Button>
        </div>
      </div>
    </div>
  )
}
