import { AlertCircle, AlertTriangle, Bell, Info } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { useMarkAllRead, useMarkRead, useNotifications, useUnreadCount, type Notification } from '@/api/notifications'
import { cx } from '@/components/ui'
import { timeAgo } from '@/lib/format'

const LEVELS = {
  urgent: { icon: AlertTriangle, tone: 'bg-red-50 text-red-600', label: 'Urgent' },
  warning: { icon: AlertCircle, tone: 'bg-amber-50 text-amber-600', label: 'Needs attention' },
  info: { icon: Info, tone: 'bg-brand-50 text-brand-600', label: 'Information' },
} as const

/** One notification; opening it marks it read and goes to the screen it's about. */
export function NotificationItem({ notification, onOpen }: { notification: Notification; onOpen?: () => void }) {
  const markRead = useMarkRead()
  const navigate = useNavigate()
  const { icon: Icon, tone, label } = LEVELS[notification.level]

  function open() {
    if (!notification.is_read) markRead.mutate(notification.id)
    onOpen?.()
    if (notification.link) navigate(notification.link)
  }

  return (
    <button
      type="button"
      onClick={open}
      className={cx(
        'flex w-full gap-3 px-4 py-3 text-left hover:bg-slate-50',
        !notification.is_read && 'bg-brand-50/40',
      )}
    >
      <span className={cx('mt-0.5 grid size-8 shrink-0 place-items-center rounded-full', tone)}>
        <Icon className="size-4" aria-hidden />
        <span className="sr-only">{label}</span>
      </span>
      <span className="min-w-0 flex-1">
        <span className={cx('block text-sm', notification.is_read ? 'text-slate-700' : 'font-medium text-slate-900')}>
          {notification.title}
        </span>
        {notification.body && <span className="block truncate text-sm text-slate-500">{notification.body}</span>}
        <span className="mt-0.5 block text-xs text-slate-400">{timeAgo(notification.created_at)}</span>
      </span>
      {!notification.is_read && (
        <span className="mt-2 size-2 shrink-0 rounded-full bg-brand-500" aria-label="Unread" />
      )}
    </button>
  )
}

/** The bell in the header: unread count, and the latest notifications in a panel. */
export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const panel = useRef<HTMLDivElement>(null)
  const { data: unread = 0 } = useUnreadCount()
  const { data, isLoading } = useNotifications({ pageSize: 8, enabled: open })
  const markAll = useMarkAllRead()

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !panel.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  return (
    <div ref={panel} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="relative rounded-lg p-2 text-slate-500 hover:bg-brand-50 hover:text-brand-700"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        title="Notifications"
      >
        <Bell className="size-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 grid min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-4 text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h2 className="font-medium text-slate-900">Notifications</h2>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markAll.mutate()}
                className="text-sm text-brand-600 hover:text-brand-700"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-[60vh] divide-y divide-slate-100 overflow-y-auto">
            {isLoading ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">Loading…</p>
            ) : data?.results.length ? (
              data.results.map((notification) => (
                <NotificationItem key={notification.id} notification={notification} onOpen={() => setOpen(false)} />
              ))
            ) : (
              <p className="px-4 py-8 text-center text-sm text-slate-500">You're all caught up.</p>
            )}
          </div>
          <Link
            to="/notifications"
            onClick={() => setOpen(false)}
            className="block border-t border-slate-100 px-4 py-2.5 text-center text-sm font-medium text-brand-600 hover:bg-slate-50"
          >
            See all notifications
          </Link>
        </div>
      )}
    </div>
  )
}
