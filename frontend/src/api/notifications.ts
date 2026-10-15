/** The signed-in person's notification centre (the bell). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type Page } from '@/lib/api'

export interface Notification {
  id: number
  kind: string
  level: 'info' | 'warning' | 'urgent'
  title: string
  body: string
  /** Screen in the app to open, e.g. /visits/12 */
  link: string
  created_at: string
  read_at: string | null
  is_read: boolean
}

const KEY = ['notifications']

/** Checked every 30 seconds, and whenever the tab regains focus. */
export function useUnreadCount() {
  return useQuery({
    queryKey: [...KEY, 'unread-count'],
    queryFn: () => api<{ count: number }>('/api/v1/notifications/unread-count/'),
    select: (data) => data.count,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
}

export function useNotifications({ unread = false, page = 1, pageSize = 20, enabled = true } = {}) {
  return useQuery({
    queryKey: [...KEY, 'list', { unread, page, pageSize }],
    queryFn: () =>
      api<Page<Notification>>('/api/v1/notifications/', {
        query: { unread: unread || undefined, page, page_size: pageSize },
      }),
    enabled,
  })
}

function useRefresh<T>(mutationFn: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn, onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }) })
}

export function useMarkRead() {
  return useRefresh((id: number) => api(`/api/v1/notifications/${id}/read/`, { method: 'POST' }))
}

export function useMarkAllRead() {
  return useRefresh(() => api('/api/v1/notifications/read-all/', { method: 'POST' }))
}
