import { useMutation } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { useState } from 'react'

import { useMarkAllRead, useNotifications, useUnreadCount } from '@/api/notifications'
import { NotificationItem } from '@/components/Notifications'
import { Button, Card, cx, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'
import { api } from '@/lib/api'
import { useAuth, useCurrentUser, type CurrentUser } from '@/lib/auth'

const EMAIL_CHOICES: { value: CurrentUser['email_notifications']; label: string }[] = [
  { value: 'all', label: 'Important notices right away, and a morning summary' },
  { value: 'important', label: 'Important notices only (emergencies, account notices)' },
  { value: 'off', label: 'No emails' },
]

/** Emails never name patients: they say what happened and link here. */
function EmailPreference() {
  const user = useCurrentUser()
  const { refreshUser } = useAuth()
  const save = useMutation({
    mutationFn: (choice: CurrentUser['email_notifications']) =>
      api('/api/v1/auth/me/', { method: 'PATCH', body: { email_notifications: choice } }),
    onSuccess: () => refreshUser(),
  })

  return (
    <Card className="mt-6 space-y-3 p-5">
      <label htmlFor="email-notifications" className="block font-medium text-slate-900">
        Email me
      </label>
      <select
        id="email-notifications"
        value={user.email_notifications}
        disabled={save.isPending}
        onChange={(event) => save.mutate(event.target.value as CurrentUser['email_notifications'])}
        className="block w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
      >
        {EMAIL_CHOICES.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
      <p className="text-sm text-slate-500">
        Sent to {user.email}. For privacy, emails never include patients' names: they say what happened and link back
        here.
      </p>
      <ErrorAlert error={save.error} />
    </Card>
  )
}

export function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useNotifications({ unread: unreadOnly, page })
  const { data: unread = 0 } = useUnreadCount()
  const markAll = useMarkAllRead()

  const show = (onlyUnread: boolean) => {
    setUnreadOnly(onlyUnread)
    setPage(1)
  }

  return (
    <>
      <PageHeader
        title="Notifications"
        description="What happened that needs you: patients waiting, results ready, prescriptions, payments and more."
        actions={
          unread > 0 && (
            <Button variant="secondary" loading={markAll.isPending} onClick={() => markAll.mutate()}>
              Mark all read
            </Button>
          )
        }
      />
      <div role="group" aria-label="Show" className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1">
        {[
          { value: false, label: 'All' },
          { value: true, label: `Unread${unread ? ` (${unread})` : ''}` },
        ].map((option) => (
          <button
            key={option.label}
            type="button"
            aria-pressed={unreadOnly === option.value}
            onClick={() => show(option.value)}
            className={cx(
              'rounded-md px-3 py-1.5 text-sm font-medium',
              unreadOnly === option.value ? 'bg-brand-500 text-white' : 'text-slate-600 hover:bg-slate-50',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
      <ErrorAlert error={error} />
      <Card className="overflow-hidden">
        {isLoading ? (
          <Spinner />
        ) : !data?.results.length ? (
          <EmptyState
            icon={<Bell className="size-5" />}
            title={unreadOnly ? "You're all caught up" : 'No notifications yet'}
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {data.results.map((notification) => (
              <NotificationItem key={notification.id} notification={notification} />
            ))}
          </div>
        )}
      </Card>
      {data && (data.next || data.previous) && (
        <div className="mt-4 flex justify-between">
          <Button variant="secondary" size="sm" disabled={!data.previous} onClick={() => setPage(page - 1)}>
            Newer
          </Button>
          <Button variant="secondary" size="sm" disabled={!data.next} onClick={() => setPage(page + 1)}>
            Older
          </Button>
        </div>
      )}
      <EmailPreference />
    </>
  )
}
