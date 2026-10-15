/** The platform operator's dashboard: hospitals, revenue, signups (platform site only). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Interval, SubscriptionPayment } from '@/api/subscription'
import { api, type Page } from '@/lib/api'
import type { Hospital, SubscriptionStatus } from '@/lib/hospital'

export type HospitalState = 'trialing' | 'paying' | 'overdue' | 'lapsed' | 'suspended'

export interface AttentionRow {
  id: number
  name: string
  domain: string
  plan: Hospital['plan']
  state: HospitalState
  current_period_end: string
  grace_ends_at: string
  days_left: number
  billing_email: string
}

export interface Overview {
  hospitals: Record<HospitalState, number> & { total: number }
  plans: Partial<Record<Hospital['plan'], number>>
  revenue: {
    monthly_recurring: string
    this_month: string
    this_month_by_plan: Partial<Record<Hospital['plan'], string>>
    by_month: { month: string; total: string }[]
  }
  signups: { last_30_days: Partial<Record<SignupStatus, number>>; stalled: number }
  attention: { trials_ending: AttentionRow[]; overdue: AttentionRow[]; lapsed: AttentionRow[] }
}

export interface PlatformHospital extends Omit<Hospital, 'domain'> {
  id: number
  schema_name: string
  domain: string | null
  domains: string[]
  is_active: boolean
  created_at: string
}

export interface HospitalDetail extends PlatformHospital {
  usage: {
    active_staff: number
    patients: number
    visits_last_30_days: number
    last_sign_in: string | null
    last_activity: string | null
  }
  payments: SubscriptionPayment[]
}

export type SignupStatus = 'pending' | 'provisioning' | 'ready' | 'failed'

export interface PlatformSignup {
  id: number
  created_at: string
  hospital_name: string
  address: string
  plan: Hospital['plan']
  first_name: string
  last_name: string
  email: string
  phone: string
  status: SignupStatus
  error: string
  verified_at: string | null
  provisioning_started_at: string | null
  completed_at: string | null
  hospital: number | null
}

/** Same rule as the API's overview: one word for where a hospital stands. */
export function hospitalState(hospital: {
  is_active: boolean
  subscription: SubscriptionStatus | null
}): HospitalState {
  const subscription = hospital.subscription
  if (!hospital.is_active) return 'suspended'
  if (!subscription) return 'trialing'
  if (subscription.access === 'read_only') return 'lapsed'
  if (subscription.access === 'warning') return 'overdue'
  return subscription.status === 'trialing' ? 'trialing' : 'paying'
}

export function useOverview() {
  return useQuery({ queryKey: ['platform', 'overview'], queryFn: () => api<Overview>('/api/v1/platform/overview/') })
}

export function useHospitals(search: string) {
  return useQuery({
    queryKey: ['platform', 'hospitals', search],
    queryFn: () => api<Page<PlatformHospital>>('/api/v1/platform/hospitals/', { query: { search, page_size: 100 } }),
    placeholderData: keepPreviousData,
  })
}

export function usePlatformHospital(id: number) {
  return useQuery({
    queryKey: ['platform', 'hospitals', 'detail', id],
    queryFn: () => api<HospitalDetail>(`/api/v1/platform/hospitals/${id}/`),
  })
}

function usePlatformMutation<T>(mutationFn: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['platform'] }),
  })
}

export function useUpdateHospital(id: number) {
  return usePlatformMutation((changes: Partial<Pick<PlatformHospital, 'plan' | 'is_active'>>) =>
    api(`/api/v1/platform/hospitals/${id}/`, { method: 'PATCH', body: changes }),
  )
}

export function useExtendAccess(id: number) {
  return usePlatformMutation((body: { days: number; reason: string }) =>
    api(`/api/v1/platform/hospitals/${id}/extend/`, { method: 'POST', body }),
  )
}

export interface ManualPayment {
  plan: Hospital['plan']
  interval: Interval
  amount: string
  reference: string
  note: string
}

export function useRecordPayment(id: number) {
  return usePlatformMutation((body: ManualPayment) =>
    api(`/api/v1/platform/hospitals/${id}/record-payment/`, { method: 'POST', body }),
  )
}

export function useSignups(filters: { status?: SignupStatus; search: string }) {
  return useQuery({
    queryKey: ['platform', 'signups', filters],
    queryFn: () =>
      api<Page<PlatformSignup>>('/api/v1/platform/signups/', {
        query: { status: filters.status, search: filters.search, page_size: 100 },
      }),
    placeholderData: keepPreviousData,
  })
}

export function useRetrySignup() {
  return usePlatformMutation((id: number) => api(`/api/v1/platform/signups/${id}/retry/`, { method: 'POST' }))
}
