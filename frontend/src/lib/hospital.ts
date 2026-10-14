import { useQuery } from '@tanstack/react-query'

import { api } from './api'
import type { Feature } from './roles'

export interface Hospital {
  name: string
  domain: string | null
  plan: 'basic' | 'pro' | 'enterprise'
  features: Feature[]
  contact_email: string
  phone: string
  address: string
  timezone: string
  currency: string
  mrn_prefix: string
}

export function useHospital() {
  return useQuery({
    queryKey: ['hospital'],
    queryFn: () => api<Hospital>('/api/v1/hospital/'),
    staleTime: 5 * 60_000,
  })
}

/** Format money in the hospital's currency, e.g. ₦12,500.00 */
export function formatMoney(amount: string | number | null | undefined, currency = 'NGN'): string {
  const value = typeof amount === 'string' ? Number(amount) : (amount ?? 0)
  try {
    return new Intl.NumberFormat('en-NG', { style: 'currency', currency }).format(value)
  } catch {
    return `${currency} ${value.toFixed(2)}`
  }
}
