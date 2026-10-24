import './index.css'

import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'

import { App } from './App'
import { CrashScreen } from './components/CrashScreen'
import { trackActivity } from './lib/activity'
import { ApiError } from './lib/api'
import { AuthProvider } from './lib/auth'
import { ErrorBoundary, initMonitoring } from './lib/monitoring'
import { currentHospital, hospitalDisplayName } from './lib/tenant'

// Without a hospital in the address, this is the platform site: landing page and signup
const PlatformSite = lazy(() =>
  import('./pages/platform/PlatformSite').then((module) => ({ default: module.PlatformSite })),
)

document.title = hospitalDisplayName()
initMonitoring()

const queryClient: QueryClient = new QueryClient({
  // A lapsed subscription refuses changes (402): refresh the hospital so the banner explains why
  mutationCache: new MutationCache({
    onError: (error) => {
      if (error instanceof ApiError && error.status === 402)
        void queryClient.invalidateQueries({ queryKey: ['hospital'] })
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Don't retry client errors (403, 404...): they won't fix themselves
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 2,
      refetchOnWindowFocus: true,
    },
  },
})

// Someone came back to an idle screen: refresh what's on it straight away
trackActivity(() => void queryClient.refetchQueries({ type: 'active' }))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* A crash shows a friendly screen (and is reported) instead of a blank page */}
    <ErrorBoundary fallback={({ resetError }) => <CrashScreen onRetry={resetError} />}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          {currentHospital() ? (
            <AuthProvider>
              <App />
            </AuthProvider>
          ) : (
            <Suspense>
              <PlatformSite />
            </Suspense>
          )}
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
