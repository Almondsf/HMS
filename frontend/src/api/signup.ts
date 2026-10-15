/** Self-serve signup on the platform site: no sign-in needed. */
import { useMutation, useQuery } from '@tanstack/react-query'

import type { PlanPrice } from '@/api/subscription'
import { api } from '@/lib/api'
import type { Hospital } from '@/lib/hospital'

export interface SignupDetails {
  hospital_name: string
  address: string
  plan: Hospital['plan']
  first_name: string
  last_name: string
  email: string
  phone: string
  password: string
  /** Honeypot: hidden from people, so only bots fill it */
  website: string
  /** Accepts the current terms of service and privacy policy */
  accept_terms: boolean
}

export interface Availability {
  address: string
  available: boolean
  reason: string
  url: string
}

export interface SignupProgress {
  status: 'pending' | 'provisioning' | 'ready' | 'failed'
  hospital_name: string
  address: string
  login_url?: string
  email?: string
  error?: string
  /** Setup has run much longer than usual (e.g. interrupted by a deploy) */
  stalled?: boolean
}

export function usePlans() {
  return useQuery({
    queryKey: ['signup', 'plans'],
    queryFn: () => api<{ trial_days: number; prices: PlanPrice[] }>('/api/v1/signup/plans/', { anonymous: true }),
    staleTime: Infinity,
  })
}

export function useAvailability(address: string) {
  return useQuery({
    queryKey: ['signup', 'availability', address],
    queryFn: ({ signal }) =>
      api<Availability>('/api/v1/signup/availability/', { query: { address }, signal, anonymous: true }),
    enabled: address.length >= 3,
    staleTime: 10_000,
  })
}

export function useSignup() {
  return useMutation({
    mutationFn: (details: SignupDetails) =>
      api<{ detail: string }>('/api/v1/signup/', { method: 'POST', body: details, anonymous: true }),
  })
}

export function useVerifySignup() {
  return useMutation({
    mutationFn: (token: string) =>
      api<SignupProgress>('/api/v1/signup/verify/', { method: 'POST', body: { token }, anonymous: true }),
  })
}

/** Poll the hospital's setup until it is ready or has failed. */
export function useSignupProgress(token: string, enabled: boolean) {
  return useQuery({
    queryKey: ['signup', 'progress', token],
    queryFn: () => api<SignupProgress>('/api/v1/signup/status/', { method: 'POST', body: { token }, anonymous: true }),
    enabled,
    refetchInterval: (query) => (query.state.data?.status === 'provisioning' ? 3000 : false),
    refetchOnWindowFocus: false,
  })
}
