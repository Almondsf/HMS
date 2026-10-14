/**
 * Error monitoring for the web app (Sentry), off unless a DSN is configured
 * (window.__HMS_CONFIG__.sentryDsn in production, VITE_SENTRY_DSN locally).
 * Like the backend, nothing identifying a patient is sent: no names or
 * emails, and URLs lose their query strings (searches can contain names).
 */
import * as Sentry from '@sentry/react'

import { currentHospital } from './tenant'

function stripQuery(url: unknown): unknown {
  return typeof url === 'string' ? url.split('?')[0] : url
}

export function initMonitoring() {
  const dsn = window.__HMS_CONFIG__?.sentryDsn || import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return

  Sentry.init({
    dsn,
    environment: window.__HMS_CONFIG__?.environment ?? import.meta.env.MODE,
    sendDefaultPii: false,
    beforeBreadcrumb(breadcrumb) {
      if (breadcrumb.data?.url) breadcrumb.data.url = stripQuery(breadcrumb.data.url)
      if (breadcrumb.category === 'navigation' && breadcrumb.data) {
        breadcrumb.data.from = stripQuery(breadcrumb.data.from)
        breadcrumb.data.to = stripQuery(breadcrumb.data.to)
      }
      // UI clicks can capture visible text, which may be a patient's name
      if (breadcrumb.category?.startsWith('ui.')) breadcrumb.message = undefined
      return breadcrumb
    },
    beforeSend(event) {
      if (event.request) {
        event.request.url = stripQuery(event.request.url) as string | undefined
        delete event.request.query_string
        delete event.request.cookies
        delete event.request.data
      }
      return event
    },
  })
  Sentry.setTag('hospital', currentHospital() ?? 'platform')
}

/** Record who is signed in by internal id and role only. */
export function setMonitoringUser(user: { id: number; user_type: string } | null) {
  Sentry.setUser(user ? { id: String(user.id) } : null)
  Sentry.setTag('role', user?.user_type ?? 'signed-out')
}

export const ErrorBoundary = Sentry.ErrorBoundary
