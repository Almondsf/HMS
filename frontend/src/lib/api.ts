import { apiBaseUrl, currentHospital } from './tenant'

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

// ---- Tokens (kept per hospital, so two hospitals in one browser don't mix) ----

export interface Tokens {
  access: string
  refresh: string
}

const hospital = currentHospital()
const storageKey = `hms.tokens.${hospital ?? 'platform'}`

export const tokenStore = {
  get(): Tokens | null {
    try {
      const raw = localStorage.getItem(storageKey)
      return raw ? (JSON.parse(raw) as Tokens) : null
    } catch {
      return null
    }
  },
  set(tokens: Tokens) {
    try {
      localStorage.setItem(storageKey, JSON.stringify(tokens))
    } catch {
      // Storage unavailable (private mode): the session lasts until reload
    }
  },
  clear() {
    try {
      localStorage.removeItem(storageKey)
    } catch {
      // ignore
    }
  },
}

/** Fired when the session can't be renewed; the auth provider signs the user out. */
export const SESSION_ENDED = 'hms:session-ended'

// ---- Requests ----

const baseUrl = hospital ? apiBaseUrl(hospital) : ''

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

async function send(path: string, options: RequestOptions, accessToken?: string): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  return fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
}

// One refresh at a time: requests that fail together all wait for the same refresh
let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const tokens = tokenStore.get()
  if (!tokens) return null
  try {
    const response = await send('/api/v1/auth/token/refresh/', { method: 'POST', body: { refresh: tokens.refresh } })
    if (!response.ok) throw new Error('refresh rejected')
    const renewed = (await response.json()) as Partial<Tokens>
    // Refresh tokens rotate: keep the new one when the server sends it
    tokenStore.set({ access: renewed.access!, refresh: renewed.refresh ?? tokens.refresh })
    return renewed.access!
  } catch {
    tokenStore.clear()
    window.dispatchEvent(new Event(SESSION_ENDED))
    return null
  }
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options, options.anonymous ? undefined : tokenStore.get()?.access)

  if (response.status === 401 && !options.anonymous && tokenStore.get()) {
    refreshing ??= refreshAccessToken().finally(() => {
      refreshing = null
    })
    const access = await refreshing
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
