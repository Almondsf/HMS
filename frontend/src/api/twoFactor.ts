/** Two-factor sign-in for the signed-in person (authenticator app codes). */
import { useMutation } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { TwoFactorStatus } from '@/lib/auth'

export interface TwoFactorSetup {
  secret: string
  otpauth_uri: string
  /** SVG data URI of the QR code to scan */
  qr_code: string
}

export type WithRecoveryCodes = TwoFactorStatus & { recovery_codes: string[] }

export function useStartTwoFactor() {
  return useMutation({
    mutationFn: () => api<TwoFactorSetup>('/api/v1/auth/two-factor/setup/', { method: 'POST' }),
  })
}

export function useConfirmTwoFactor() {
  return useMutation({
    mutationFn: (code: string) =>
      api<WithRecoveryCodes>('/api/v1/auth/two-factor/confirm/', { method: 'POST', body: { code } }),
  })
}

export function useNewRecoveryCodes() {
  return useMutation({
    mutationFn: (code: string) =>
      api<WithRecoveryCodes>('/api/v1/auth/two-factor/recovery-codes/', { method: 'POST', body: { code } }),
  })
}

export function useDisableTwoFactor() {
  return useMutation({
    mutationFn: (body: { password: string; code: string }) =>
      api<TwoFactorStatus>('/api/v1/auth/two-factor/disable/', { method: 'POST', body }),
  })
}
