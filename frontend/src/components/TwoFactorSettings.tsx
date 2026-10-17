import { CheckCircle2, Copy, Download, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import {
  useConfirmTwoFactor,
  useDisableTwoFactor,
  useNewRecoveryCodes,
  useStartTwoFactor,
  type TwoFactorSetup,
} from '@/api/twoFactor'
import { Badge, Button, Card, ErrorAlert, Input } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useAuth, useCurrentUser } from '@/lib/auth'
import { productName } from '@/lib/tenant'

function fieldError(error: unknown, field: string) {
  return error instanceof ApiError ? error.fieldErrors[field] : undefined
}

/** Shown once: the person must save them before moving on. */
function RecoveryCodes({ codes, onDone, doneLabel }: { codes: string[]; onDone: () => void; doneLabel: string }) {
  const [saved, setSaved] = useState(false)
  const [copied, setCopied] = useState(false)
  const text = `${productName()} recovery codes (each works once)\n\n${codes.join('\n')}\n`

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    const link = Object.assign(document.createElement('a'), { href: url, download: 'recovery-codes.txt' })
    document.body.append(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center gap-2 text-emerald-700">
        <CheckCircle2 className="size-5" aria-hidden />
        <h2 className="font-medium">Save your recovery codes</h2>
      </div>
      <p className="text-sm text-slate-600">
        If you lose your phone, sign in with one of these instead of a code. Each works once. Keep them somewhere safe,
        like a password manager: <strong>they won't be shown again.</strong>
      </p>
      <ul className="grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-4 font-mono text-sm text-slate-900 sm:grid-cols-5">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          icon={<Copy className="size-4" />}
          onClick={() => void navigator.clipboard.writeText(text).then(() => setCopied(true))}
        >
          {copied ? 'Copied' : 'Copy'}
        </Button>
        <Button variant="secondary" size="sm" icon={<Download className="size-4" />} onClick={download}>
          Download
        </Button>
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={saved}
          onChange={(event) => setSaved(event.target.checked)}
          className="size-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
        />
        I've saved my recovery codes
      </label>
      <Button disabled={!saved} onClick={onDone}>
        {doneLabel}
      </Button>
    </Card>
  )
}

function SetUp({ onCodes }: { onCodes: (codes: string[]) => void }) {
  const { refreshUser } = useAuth()
  const start = useStartTwoFactor()
  const confirm = useConfirmTwoFactor()
  const [code, setCode] = useState('')
  const setup: TwoFactorSetup | undefined = start.data

  function handleConfirm(event: FormEvent) {
    event.preventDefault()
    confirm.mutate(code.trim(), {
      onSuccess: (result) => {
        onCodes(result.recovery_codes)
        void refreshUser()
      },
    })
  }

  if (!setup) {
    return (
      <Card className="space-y-4 p-5">
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-700">
          <li>Install an authenticator app on your phone: Google Authenticator, Microsoft Authenticator or similar.</li>
          <li>Scan the QR code we show you.</li>
          <li>Enter the 6-digit code the app shows.</li>
        </ol>
        <ErrorAlert error={start.error} />
        <Button icon={<ShieldCheck className="size-4" />} loading={start.isPending} onClick={() => start.mutate()}>
          Set up two-factor sign-in
        </Button>
      </Card>
    )
  }

  return (
    <Card className="space-y-5 p-5">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <img
          src={setup.qr_code}
          alt="QR code to scan with your authenticator app"
          className="size-44 shrink-0 self-center rounded-lg border border-slate-200 bg-white p-1"
        />
        <div className="space-y-2 text-sm text-slate-600">
          <p>Scan this with your authenticator app.</p>
          <p>Can't scan it? In the app, choose to enter a key, and type:</p>
          <p className="break-all rounded-lg bg-slate-50 p-3 font-mono text-slate-900">
            {setup.secret.match(/.{1,4}/g)?.join(' ')}
          </p>
        </div>
      </div>
      <form onSubmit={handleConfirm} className="flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
        <div className="w-48">
          <Input
            label="6-digit code from the app"
            autoComplete="one-time-code"
            inputMode="numeric"
            required
            value={code}
            onChange={(event) => setCode(event.target.value)}
            error={fieldError(confirm.error, 'code')}
          />
        </div>
        <Button type="submit" loading={confirm.isPending}>
          Turn on
        </Button>
      </form>
      {!fieldError(confirm.error, 'code') && <ErrorAlert error={confirm.error} />}
    </Card>
  )
}

function Manage({ onCodes }: { onCodes: (codes: string[]) => void }) {
  const user = useCurrentUser()
  const { refreshUser } = useAuth()
  const renew = useNewRecoveryCodes()
  const disable = useDisableTwoFactor()
  const [renewCode, setRenewCode] = useState('')
  const [password, setPassword] = useState('')
  const [offCode, setOffCode] = useState('')
  const status = user.two_factor

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3 p-5">
        <ShieldCheck className="size-5 text-emerald-600" aria-hidden />
        <span className="font-medium text-slate-900">Two-factor sign-in is on</span>
        <Badge tone={status.recovery_codes_left > 2 ? 'gray' : 'amber'}>
          {status.recovery_codes_left} recovery code{status.recovery_codes_left === 1 ? '' : 's'} left
        </Badge>
      </Card>

      <Card className="p-5">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            renew.mutate(renewCode.trim(), { onSuccess: (result) => onCodes(result.recovery_codes) })
          }}
          className="space-y-3"
        >
          <h2 className="font-medium text-slate-900">New recovery codes</h2>
          <p className="text-sm text-slate-500">Replaces your old codes, for example if you've used most of them.</p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-48">
              <Input
                label="Code from the app"
                autoComplete="one-time-code"
                inputMode="numeric"
                required
                value={renewCode}
                onChange={(event) => setRenewCode(event.target.value)}
                error={fieldError(renew.error, 'code')}
              />
            </div>
            <Button type="submit" variant="secondary" loading={renew.isPending}>
              Get new codes
            </Button>
          </div>
        </form>
      </Card>

      {status.required ? (
        <p className="text-sm text-slate-500">
          Your role requires two-factor sign-in, so it can't be turned off. New phone? Ask another administrator to
          reset it, then set it up again.
        </p>
      ) : (
        <Card className="p-5">
          <form
            onSubmit={(event) => {
              event.preventDefault()
              disable.mutate({ password, code: offCode.trim() }, { onSuccess: () => void refreshUser() })
            }}
            className="space-y-3"
          >
            <h2 className="font-medium text-slate-900">Turn off</h2>
            <p className="text-sm text-slate-500">To move to a new phone, turn it off and set it up again.</p>
            <div className="grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end">
              <Input
                label="Password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                error={fieldError(disable.error, 'password')}
              />
              <Input
                label="Code from the app"
                autoComplete="one-time-code"
                required
                value={offCode}
                onChange={(event) => setOffCode(event.target.value)}
                error={fieldError(disable.error, 'code')}
              />
              <Button type="submit" variant="danger" loading={disable.isPending}>
                Turn off
              </Button>
            </div>
            {!fieldError(disable.error, 'password') && !fieldError(disable.error, 'code') && (
              <ErrorAlert error={disable.error} />
            )}
          </form>
        </Card>
      )}
    </div>
  )
}

/** Set up, manage or turn off two-factor sign-in for the signed-in person. */
export function TwoFactorSettings({ onFinished }: { onFinished?: () => void }) {
  const user = useCurrentUser()
  const [codes, setCodes] = useState<string[] | null>(null)

  if (codes) {
    return (
      <RecoveryCodes
        codes={codes}
        doneLabel={onFinished ? 'Continue' : 'Done'}
        onDone={() => {
          setCodes(null)
          onFinished?.()
        }}
      />
    )
  }
  return (
    <div className="space-y-4">
      {user.two_factor.required && !user.two_factor.enabled && (
        <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Your role requires two-factor sign-in: a code from your phone as well as your password. Set it up to continue.
        </p>
      )}
      {user.two_factor.enabled ? <Manage onCodes={setCodes} /> : <SetUp onCodes={setCodes} />}
    </div>
  )
}
