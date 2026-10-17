import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'

import { Button, ErrorAlert, Input } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { hospitalDisplayName } from '@/lib/tenant'

export function LoginPage({
  home = '/',
  title,
  allowReset = true,
}: {
  /** Where to go after signing in, unless the person was sent here from a page */
  home?: string
  title?: string
  /** Offer "Forgot password?" (hospital sites); platform operators reset from the server */
  allowReset?: boolean
} = {}) {
  const { user, login, verifyTwoFactor } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const hospitalName = title ?? hospitalDisplayName()
  // Prefilled when arriving from the signup page
  const [email, setEmail] = useState(() => new URLSearchParams(location.search).get('email') ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)
  // Two-factor step: the password was right, now the code from the app (or a recovery code)
  const [challenge, setChallenge] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [recovery, setRecovery] = useState(false)

  const state = location.state as { from?: string; notice?: string } | null
  const returnTo = state?.from ?? home
  if (user) return <Navigate to={returnTo} replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (challenge) {
        await verifyTwoFactor(challenge, code)
      } else {
        const result = await login(email.trim(), password)
        if ('challenge' in result) {
          setChallenge(result.challenge)
          return
        }
      }
      navigate(returnTo, { replace: true })
    } catch (caught) {
      setError(caught)
      // An expired step means starting again from the password
      if (
        challenge &&
        caught instanceof ApiError &&
        caught.data &&
        (caught.data as { code?: string }).code === 'challenge_expired'
      ) {
        setChallenge(null)
      }
    } finally {
      setSubmitting(false)
    }
  }

  function startOver() {
    setChallenge(null)
    setCode('')
    setRecovery(false)
    setError(null)
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
          <p className="mt-1 text-sm text-slate-500">{challenge ? 'Two-factor sign-in' : 'Sign in to continue'}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {state?.notice && !error && (
            <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
              {state.notice}
            </p>
          )}
          <ErrorAlert error={error} />
          {challenge ? (
            <>
              <Input
                key={recovery ? 'recovery' : 'code'}
                label={recovery ? 'Recovery code' : 'Code from your authenticator app'}
                autoComplete="one-time-code"
                inputMode={recovery ? 'text' : 'numeric'}
                placeholder={recovery ? 'xxxx-xxxx' : '123456'}
                required
                autoFocus
                value={code}
                onChange={(event) => setCode(event.target.value)}
                hint={recovery ? 'Each recovery code works once.' : 'The 6-digit code changes every 30 seconds.'}
              />
              <Button type="submit" loading={submitting} className="w-full">
                Verify
              </Button>
              <div className="flex justify-between text-sm">
                <button type="button" onClick={startOver} className="text-slate-600 hover:text-slate-900">
                  Back
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRecovery(!recovery)
                    setCode('')
                  }}
                  className="text-brand-600 hover:text-brand-700"
                >
                  {recovery ? 'Use the app instead' : 'Lost your phone? Use a recovery code'}
                </button>
              </div>
            </>
          ) : (
            <>
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
              {allowReset && (
                <p className="text-center text-sm">
                  <Link to="/forgot-password" className="text-brand-600 hover:text-brand-700">
                    Forgot password?
                  </Link>
                </p>
              )}
            </>
          )}
        </form>
      </div>
    </div>
  )
}
