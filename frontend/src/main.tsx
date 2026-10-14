import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'

import { App } from './App'
import { CrashScreen } from './components/CrashScreen'
import { ApiError } from './lib/api'
import { AuthProvider } from './lib/auth'
import { ErrorBoundary, initMonitoring } from './lib/monitoring'
import { hospitalDisplayName } from './lib/tenant'

document.title = hospitalDisplayName()
initMonitoring()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Don't retry client errors (403, 404...): they won't fix themselves
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 2,
      refetchOnWindowFocus: true,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* A crash shows a friendly screen (and is reported) instead of a blank page */}
    <ErrorBoundary fallback={({ resetError }) => <CrashScreen onRetry={resetError} />}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
