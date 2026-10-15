import { CheckCircle2, Mail, MessageSquare, XCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import {
  useProviders,
  useSaveProvider,
  useSwitchProvider,
  useTestProvider,
  type ProviderChannel,
  type ProviderInfo,
  type ProviderSetup,
} from '@/api/platform'
import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

const CHANNELS: { channel: ProviderChannel; title: string; icon: typeof Mail; testLabel: string; testHint: string }[] =
  [
    {
      channel: 'email',
      title: 'Email',
      icon: Mail,
      testLabel: 'Send a test email to',
      testHint: 'you@yourdomain.com',
    },
    {
      channel: 'sms',
      title: 'SMS',
      icon: MessageSquare,
      testLabel: 'Send a test SMS to',
      testHint: '0803 123 4567',
    },
  ]

function StatusBadge({ setup }: { setup?: ProviderSetup }) {
  if (!setup) return <Badge>Not set up</Badge>
  if (setup.is_active) return <Badge tone="green">In use</Badge>
  if (setup.last_test_ok) return <Badge tone="brand">Tested, ready</Badge>
  if (setup.last_test_ok === false) return <Badge tone="red">Test failed</Badge>
  return <Badge tone="amber">Not tested</Badge>
}

function ProviderCard({
  info,
  setup,
  testLabel,
  testHint,
}: {
  info: ProviderInfo
  setup?: ProviderSetup
  testLabel: string
  testHint: string
}) {
  const save = useSaveProvider(info.channel, info.name)
  const test = useTestProvider(info.channel, info.name)
  const switchTo = useSwitchProvider(info.channel)
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      info.fields.map((field) => [field.name, field.secret ? '' : (setup?.settings[field.name] ?? field.default)]),
    ),
  )
  const [to, setTo] = useState('')
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {}

  const isSecret = (name: string) => info.fields.some((field) => field.name === name && field.secret)
  const secretsCleared = () =>
    Object.fromEntries(info.fields.filter((field) => field.secret).map((field) => [field.name, '']))

  function handleSave(event: FormEvent) {
    event.preventDefault()
    // Blank secret fields keep the saved value
    const body = Object.fromEntries(Object.entries(values).filter(([name, value]) => value || !isSecret(name)))
    save.mutate(body, {
      onSuccess: () => setValues((current) => ({ ...current, ...secretsCleared() })),
    })
  }

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-medium text-slate-900">{info.label}</h3>
        <StatusBadge setup={setup} />
      </div>

      {info.fields.length > 0 && (
        <form onSubmit={handleSave} className="space-y-3">
          {info.fields.map((field) => (
            <Input
              key={field.name}
              label={field.required ? field.label : `${field.label} (optional)`}
              type={field.secret ? 'password' : 'text'}
              autoComplete="off"
              value={values[field.name] ?? ''}
              onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
              placeholder={
                field.secret && setup?.secrets[field.name]
                  ? `${setup.secrets[field.name]} saved: leave blank to keep`
                  : field.default
              }
              error={errors[field.name]}
              hint={field.help}
            />
          ))}
          <ErrorAlert error={Object.keys(errors).length ? null : save.error} />
          <div className="flex items-center gap-3">
            <Button type="submit" variant="secondary" size="sm" loading={save.isPending}>
              Save settings
            </Button>
            {save.isSuccess && <span className="text-sm text-emerald-700">Saved. Send a test next.</span>}
          </div>
        </form>
      )}

      {(setup || info.fields.length === 0) && (
        <div className="space-y-3 border-t border-slate-100 pt-4">
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (!setup && info.fields.length === 0) save.mutate({}, { onSuccess: () => test.mutate(to) })
              else test.mutate(to)
            }}
            className="flex flex-wrap items-end gap-3"
          >
            <div className="min-w-56 flex-1">
              <Input
                label={testLabel}
                required
                value={to}
                onChange={(event) => setTo(event.target.value)}
                placeholder={testHint}
              />
            </div>
            <Button type="submit" variant="secondary" size="sm" loading={test.isPending}>
              Send test
            </Button>
          </form>
          <ErrorAlert error={test.error} />
          {setup?.last_tested_at && (
            <p
              className={`flex items-start gap-1.5 text-sm ${setup.last_test_ok ? 'text-emerald-700' : 'text-red-700'}`}
            >
              {setup.last_test_ok ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden />
              ) : (
                <XCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              )}
              <span>
                {setup.last_test_ok ? 'Test sent' : `Test failed: ${setup.last_test_error}`} ·{' '}
                {formatDateTime(setup.last_tested_at)}
                {setup.last_test_ok && ' (check it arrived)'}
              </span>
            </p>
          )}
        </div>
      )}

      {setup && (
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
          {setup.is_active ? (
            <Button variant="secondary" size="sm" loading={switchTo.isPending} onClick={() => switchTo.mutate(null)}>
              Stop using (back to server settings)
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={!setup.last_test_ok || !info.delivers}
              loading={switchTo.isPending}
              onClick={() => {
                if (window.confirm(`Switch all ${info.channel === 'email' ? 'email' : 'SMS'} to ${info.label} now?`)) {
                  switchTo.mutate(info.name)
                }
              }}
            >
              Use {info.label.split(' (')[0]}
            </Button>
          )}
          {!info.delivers && (
            <span className="text-sm text-slate-500">For development only: it just prints messages.</span>
          )}
          {info.delivers && !setup.last_test_ok && !setup.is_active && (
            <span className="text-sm text-slate-500">Send a successful test first.</span>
          )}
          <ErrorAlert error={switchTo.error} />
        </div>
      )}
    </Card>
  )
}

export function ProvidersPage() {
  const { data, isLoading, error } = useProviders()
  if (isLoading) return <Spinner />
  if (!data) return <ErrorAlert error={error} />

  return (
    <>
      <PageHeader
        title="Providers"
        description="Who delivers your email and SMS. Switch at any time: test first, then use. Keys are stored encrypted and never shown again."
      />
      <div className="space-y-10">
        {CHANNELS.map(({ channel, title, icon: Icon, testLabel, testHint }) => {
          const status = data.channels[channel]
          return (
            <section key={channel}>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <Icon className="size-5 text-brand-600" aria-hidden />
                <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
                <span className="text-sm text-slate-600">
                  Now sending with <span className="font-medium text-slate-900">{status.using}</span>
                  {status.source === 'server settings' && ' (server settings)'}
                </span>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                {data.catalog
                  .filter((info) => info.channel === channel)
                  .sort((a, b) => Number(b.delivers) - Number(a.delivers))
                  .map((info) => (
                    <ProviderCard
                      key={info.name}
                      info={info}
                      setup={data.configs.find((setup) => setup.channel === channel && setup.provider === info.name)}
                      testLabel={testLabel}
                      testHint={testHint}
                    />
                  ))}
              </div>
            </section>
          )
        })}
      </div>
    </>
  )
}
