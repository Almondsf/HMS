/**
 * Which hospital this browser tab belongs to, from its address:
 * stlukes.hms.app -> "stlukes", main.localhost -> "main".
 */

const BASE_DOMAIN: string = import.meta.env.VITE_TENANT_BASE_DOMAIN ?? 'localhost'

export function currentHospital(hostname = window.location.hostname): string | null {
  const suffix = `.${BASE_DOMAIN}`
  if (!hostname.endsWith(suffix)) return null
  const subdomain = hostname.slice(0, -suffix.length)
  return /^[a-z0-9-]+$/.test(subdomain) ? subdomain : null
}

/**
 * Where the hospital's API lives. VITE_API_URL may contain {hospital}, e.g.
 * "https://{hospital}.api.hms.app". Empty means the same origin (the API is
 * served behind the same domain). Locally: http://<hospital>.localhost:8000.
 */
export function apiBaseUrl(hospital: string): string {
  const template: string | undefined = import.meta.env.VITE_API_URL
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
