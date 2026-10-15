/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The product's name in development (production uses the PRODUCT_NAME setting). */
  readonly VITE_PRODUCT_NAME?: string
  /** Domain hospitals live under, e.g. "hms.app" (default "localhost"). */
  readonly VITE_TENANT_BASE_DOMAIN?: string
  /** API address; may contain {hospital}. Empty string = same origin. */
  readonly VITE_API_URL?: string
  /** Sentry DSN for local testing of error monitoring (optional). */
  readonly VITE_SENTRY_DSN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
