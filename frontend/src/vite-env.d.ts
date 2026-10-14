/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Domain hospitals live under, e.g. "hms.app" (default "localhost"). */
  readonly VITE_TENANT_BASE_DOMAIN?: string
  /** API address; may contain {hospital}. Empty string = same origin. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
