/** The hospital's subscription to the platform: prices, Paystack checkout, payment history. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Hospital, SubscriptionStatus } from '@/lib/hospital'

export type Interval = 'monthly' | 'yearly'

export interface PlanPrice {
  plan: Hospital['plan']
  interval: Interval
  amount: string
  currency: string
}

export interface SubscriptionPayment {
  reference: string
  source: 'paystack' | 'manual'
  plan: Hospital['plan']
  interval: Interval
  amount: string
  currency: string
  paid_at: string
  period_end: string
}

export interface SubscriptionSummary extends SubscriptionStatus {
  plan: Hospital['plan']
  /** False until the platform configures Paystack; payments are then by bank transfer. */
  online_payments: boolean
  prices?: PlanPrice[]
  payments?: SubscriptionPayment[]
}

const KEY = ['subscription']

export function useSubscription() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => api<SubscriptionSummary>('/api/v1/subscription/'),
  })
}

function useRefreshAfter<T>(mutationFn: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY })
      // The plan (and so the modules) and the banner live on the hospital
      void queryClient.invalidateQueries({ queryKey: ['hospital'] })
    },
  })
}

export function useCheckout() {
  return useMutation({
    mutationFn: (choice: { plan: Hospital['plan']; interval: Interval }) =>
      api<{ authorization_url: string; reference: string }>('/api/v1/subscription/checkout/', {
        method: 'POST',
        body: choice,
      }),
  })
}

export function useConfirmPayment() {
  return useRefreshAfter((reference: string) =>
    api<SubscriptionSummary>('/api/v1/subscription/confirm/', {
      method: 'POST',
      body: { reference },
    }),
  )
}

export function useCancelAutoRenew() {
  return useRefreshAfter(() =>
    api<SubscriptionSummary>('/api/v1/subscription/cancel/', {
      method: 'POST',
    }),
  )
}
