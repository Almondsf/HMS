import { apiBaseUrl, currentHospital, platformApiBaseUrl } from './tenant'

/** An error response from the API, with field errors when it was a validation error. */
export class ApiError extends Error {
  readonly status: number
  readonly data: unknown

  constructor(status: number, data: unknown) {
    super(messageFrom(data, status))
    this.status = status
    this.data = data
  }

  /** {field: "first message"} for validation errors, e.g. to show under form inputs. */
  get fieldErrors(): Record<string, string> {
    if (!this.data || typeof this.data !== 'object' || Array.isArray(this.data)) return {}
    const errors: Record<string, string> = {}
    for (const [field, value] of Object.entries(this.data as Record<string, unknown>)) {
      const first = Array.isArray(value) ? value[0] : value
      if (typeof first === 'string') errors[field] = first
    }
    return errors
  }
}

function messageFrom(data: unknown, status: number): string {
  if (typeof data === 'string' && data) return data
  if (Array.isArray(data) && typeof data[0] === 'string') return data[0]
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    if (typeof record.detail === 'string') return record.detail
    for (const value of Object.values(record)) {
      const first = Array.isArray(value) ? value[0] : value
      if (typeof first === 'string') return first
    }
  }
  if (status >= 500) return 'Something went wrong on our side. Please try again.'
  return 'Request failed.'
}

// ---- Session ----
//
// The refresh token lives in an httpOnly cookie set by the API (cookie mode):
// page scripts can't read it, so an injected script can't steal the session.
// The short-lived access token is kept in memory only; after a reload the
// session is restored from the cookie (see restoreSession).

const hospital = currentHospital()
let accessToken: string | null = null

export const session = {
  get access() {
    return accessToken
  },
  set(access: string | null) {
    accessToken = access
  },
}

/** Sent on auth requests so the API uses the cookie instead of the JSON body. */
const COOKIE_MODE = { 'X-HMS-Auth-Mode': 'cookie' }

/** Fired when the session can't be renewed; the auth provider signs the user out. */
export const SESSION_ENDED = 'hms:session-ended'

// ---- Requests ----

// No hospital in the address: this is the platform site (landing page, signup)
const baseUrl = hospital ? apiBaseUrl(hospital) : platformApiBaseUrl()

type Query = Record<string, string | number | boolean | null | undefined>

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Query
  signal?: AbortSignal
  /** Don't try to refresh the session on 401 (login, refresh itself). */
  anonymous?: boolean
}

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${baseUrl}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }
  return url.toString()
}

async function send(path: string, options: RequestOptions, access?: string | null): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json', ...COOKIE_MODE }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (access) headers.Authorization = `Bearer ${access}`
  return fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
    credentials: 'include', // send the refresh cookie (the API is on another port/host)
  })
}

// Refresh tokens rotate (each use revokes the previous one), so two refreshes
// sent at once with the same cookie would fail. Everyone shares one in flight:
// requests that hit 401 together, and React running start-up effects twice.
let refreshing: Promise<string | null> | null = null

async function requestNewAccessToken(): Promise<string | null> {
  try {
    const response = await send('/api/v1/auth/token/refresh/', { method: 'POST', body: {} })
    if (!response.ok) return null
    const { access } = (await response.json()) as { access: string }
    session.set(access)
    return access
  } catch {
    return null
  }
}

/** Get a new access token using the refresh cookie; null if there's no valid session. */
export function restoreSession(): Promise<string | null> {
  refreshing ??= requestNewAccessToken().finally(() => {
    refreshing = null
  })
  return refreshing
}

async function refreshAccessToken(): Promise<string | null> {
  const access = await restoreSession()
  if (!access) {
    session.set(null)
    window.dispatchEvent(new Event(SESSION_ENDED))
  }
  return access
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options, options.anonymous ? undefined : session.access)

  if (response.status === 401 && !options.anonymous && session.access) {
    const access = await refreshAccessToken()
    if (access) response = await send(path, options, access)
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, data)
  }
  if (response.status === 204 || response.status === 205) return undefined as T
  return (await response.json()) as T
}

/** DRF's paginated list response. */
export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
