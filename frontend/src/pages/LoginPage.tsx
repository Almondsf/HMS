import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'

import { Button, ErrorAlert, Input } from '@/components/ui'
import { useAuth } from '@/lib/auth'
import { hospitalDisplayName } from '@/lib/tenant'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const hospitalName = hospitalDisplayName()
  // Prefilled when arriving from the signup page
  const [email, setEmail] = useState(() => new URLSearchParams(location.search).get('email') ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)

  const state = location.state as { from?: string; notice?: string } | null
  const returnTo = state?.from ?? '/'
  if (user) return <Navigate to={returnTo} replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email.trim(), password)
      navigate(returnTo, { replace: true })
    } catch (caught) {
      setError(caught)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-b from-brand-50 to-white px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div
            className="mb-4 grid size-12 place-items-center rounded-xl bg-brand-500 text-white shadow-sm"
            aria-hidden
          >
            <svg viewBox="0 0 24 24" className="size-6" fill="currentColor">
              <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-slate-900">{hospitalName}</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {state?.notice && !error && (
            <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
              {state.notice}
            </p>
          )}
          <ErrorAlert error={error} />
          <Input
            label="Email"
            type="email"
            autoComplete="username"
            required
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Input
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <Button type="submit" loading={submitting} className="w-full">
            Sign in
          </Button>
          <p className="text-center text-sm">
            <Link to="/forgot-password" className="text-brand-600 hover:text-brand-700">
              Forgot password?
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
