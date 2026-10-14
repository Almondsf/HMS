import { KeyRound, MailCheck } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { Button, Card, ErrorAlert, Input, PageHeader } from '@/components/ui'
import { api, ApiError } from '@/lib/api'
import { useAuth, useCurrentUser } from '@/lib/auth'
import { hospitalDisplayName } from '@/lib/tenant'

function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-b from-brand-50 to-white px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <p className="text-sm font-medium text-brand-700">{hospitalDisplayName()}</p>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">{children}</div>
      </div>
    </div>
  )
}

/** Two matching password fields; returns an error message, or null when fine. */
function usePasswordPair() {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const mismatch = confirm !== '' && password !== confirm ? "The passwords don't match." : null
  return { password, setPassword, confirm, setConfirm, mismatch, ready: password.length > 0 && password === confirm }
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const response = await api<{ detail: string }>('/api/v1/auth/password/forgot/', {
        method: 'POST',
        body: { email: email.trim() },
        anonymous: true,
      })
      setSent(response.detail)
    } catch (caught) {
      setError(caught)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a link to choose a new one.">
      {sent ? (
        <div className="space-y-4 text-center">
          <MailCheck className="mx-auto size-8 text-brand-500" aria-hidden />
          <p className="text-sm text-slate-700">{sent}</p>
          <p className="text-xs text-slate-500">The link works once and expires after an hour.</p>
          <Link to="/login" className="text-sm font-medium text-brand-600 hover:text-brand-700">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <ErrorAlert error={error} />
          <Input label="Email" type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" loading={submitting} className="w-full">
            Send reset link
          </Button>
          <p className="text-center text-sm">
            <Link to="/login" className="text-brand-600 hover:text-brand-700">
              Back to sign in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const pair = usePasswordPair()
  const [error, setError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)
  const uid = params.get('uid')
  const token = params.get('token')
  const fieldErrors = error instanceof ApiError ? error.fieldErrors : {}

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api('/api/v1/auth/password/reset/', {
        method: 'POST',
        body: { uid, token, new_password: pair.password },
        anonymous: true,
      })
      navigate('/login', { replace: true, state: { notice: 'Password changed. Sign in with your new password.' } })
    } catch (caught) {
      setError(caught)
    } finally {
      setSubmitting(false)
    }
  }

  if (!uid || !token) {
    return (
      <AuthShell title="Reset link incomplete">
        <p className="text-sm text-slate-600">
          Open the link from the email exactly as it was sent, or{' '}
          <Link to="/forgot-password" className="font-medium text-brand-600">
            request a new one
          </Link>
          .
        </p>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Choose a new password">
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorAlert error={fieldErrors.token ? new Error(fieldErrors.token) : Object.keys(fieldErrors).length ? null : error} />
        {fieldErrors.token && (
          <Link to="/forgot-password" className="block text-sm font-medium text-brand-600">
            Request a new link
          </Link>
        )}
        <Input
          label="New password"
          type="password"
          autoComplete="new-password"
          required
          autoFocus
          value={pair.password}
          onChange={(e) => pair.setPassword(e.target.value)}
          error={fieldErrors.new_password}
          hint="At least 10 characters, not a common password"
        />
        <Input
          label="Repeat it"
          type="password"
          autoComplete="new-password"
          required
          value={pair.confirm}
          onChange={(e) => pair.setConfirm(e.target.value)}
          error={pair.mismatch ?? undefined}
        />
        <Button type="submit" loading={submitting} disabled={!pair.ready} className="w-full">
          Save password
        </Button>
      </form>
    </AuthShell>
  )
}

export function ChangePasswordPage() {
  const user = useCurrentUser()
  const { logout } = useAuth()
  const navigate = useNavigate()
  const pair = usePasswordPair()
  const [current, setCurrent] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)
  const fieldErrors = error instanceof ApiError ? error.fieldErrors : {}

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api('/api/v1/auth/password/change/', {
        method: 'POST',
        body: { old_password: current, new_password: pair.password },
      })
      // Changing the password signs out every session, including this one
      await logout()
      navigate('/login', { replace: true, state: { notice: 'Password changed. Sign in with your new password.' } })
    } catch (caught) {
      setError(caught)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-md">
      <PageHeader
        title={user.must_change_password ? 'Choose your own password' : 'Change password'}
        description={
          user.must_change_password
            ? 'You signed in with a temporary password. Set a new one to continue.'
            : 'You will be signed out everywhere and asked to sign in again.'
        }
      />
      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <ErrorAlert error={Object.keys(fieldErrors).length ? null : error} />
          <Input
            label={user.must_change_password ? 'Temporary password' : 'Current password'}
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            error={fieldErrors.old_password}
          />
          <Input
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            value={pair.password}
            onChange={(e) => pair.setPassword(e.target.value)}
            error={fieldErrors.new_password}
            hint="At least 10 characters, not a common password"
          />
          <Input
            label="Repeat it"
            type="password"
            autoComplete="new-password"
            required
            value={pair.confirm}
            onChange={(e) => pair.setConfirm(e.target.value)}
            error={pair.mismatch ?? undefined}
          />
          <Button type="submit" loading={submitting} disabled={!pair.ready} icon={<KeyRound className="size-4" />}>
            Change password
          </Button>
        </form>
      </Card>
    </div>
  )
}
