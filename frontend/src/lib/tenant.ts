/**
 * Which hospital this browser tab belongs to, from its address:
 * stlukes.hms.app -> "stlukes", main.localhost -> "main".
 *
 * In production Django serves the app and injects window.__HMS_CONFIG__
 * (see hms/spa.py), so one build works on any domain. In local development
 * the Vite env variables (or their defaults) apply.
 */

interface RuntimeConfig {
  tenantBaseDomain?: string
  /** API address; '' = same origin. May contain {hospital}. */
  apiUrl?: string
}

declare global {
  interface Window {
    __HMS_CONFIG__?: RuntimeConfig
  }
}

const runtime: RuntimeConfig = window.__HMS_CONFIG__ ?? {}

const BASE_DOMAIN: string = runtime.tenantBaseDomain ?? import.meta.env.VITE_TENANT_BASE_DOMAIN ?? 'localhost'

export function currentHospital(hostname = window.location.hostname): string | null {
  const suffix = `.${BASE_DOMAIN}`
  if (!hostname.endsWith(suffix)) return null
  const subdomain = hostname.slice(0, -suffix.length)
  return /^[a-z0-9-]+$/.test(subdomain) ? subdomain : null
}

/**
 * Where the hospital's API lives. May contain {hospital}, e.g.
 * "https://{hospital}.api.hms.app". Empty means the same origin. Locally the
 * default is http://<hospital>.localhost:8000.
 */
export function apiBaseUrl(hospital: string): string {
  const template = runtime.apiUrl ?? import.meta.env.VITE_API_URL
  if (template === '') return ''
  return (template ?? `${window.location.protocol}//{hospital}.localhost:8000`).replace('{hospital}', hospital)
}

/** A readable name from the address until the real one loads after sign-in: st-lukes -> "St Lukes". */
export function hospitalDisplayName(hospital = currentHospital()): string {
  if (!hospital) return 'HMS'
  return hospital
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
