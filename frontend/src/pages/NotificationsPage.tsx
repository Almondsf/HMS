import { Bell } from 'lucide-react'
import { useState } from 'react'

import { useMarkAllRead, useNotifications, useUnreadCount } from '@/api/notifications'
import { NotificationItem } from '@/components/Notifications'
import { Button, Card, cx, EmptyState, ErrorAlert, PageHeader, Spinner } from '@/components/ui'

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
          <EmptyState icon={<Bell className="size-5" />} title={unreadOnly ? "You're all caught up" : 'No notifications yet'} />
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
    </>
  )
}
