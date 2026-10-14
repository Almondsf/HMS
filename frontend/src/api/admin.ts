/** Staff accounts, departments, hospital settings and reports. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { StaffMember } from '@/api/frontDesk'
import { api, type Page } from '@/lib/api'
import type { Hospital } from '@/lib/hospital'

export type StaffRole = 'doctor' | 'nurse' | 'lab_tech' | 'pharmacist' | 'receptionist' | 'cashier'

/** Registration endpoint per role: /api/v1/create-profile/<path>/ */
export const STAFF_ENDPOINTS: Record<StaffRole, string> = {
  doctor: 'doctors',
  nurse: 'nurses',
  lab_tech: 'labtechs',
  pharmacist: 'pharmacists',
  receptionist: 'receptionists',
  cashier: 'cashiers',
}

export interface Department {
  id: number
  name: string
  description: string
  is_active: boolean
}

export function useStaff(filters: { role?: string; search?: string; is_active?: boolean }) {
  return useQuery({
    queryKey: ['staff', 'list', filters],
    queryFn: () =>
      api<Page<StaffMember>>('/api/v1/staff/', {
        query: { role: filters.role, search: filters.search, is_active: filters.is_active, page_size: 100 },
      }),
    select: (page) => page.results,
  })
}

export function useCreateStaff() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ role, ...body }: { role: StaffRole } & Record<string, unknown>) =>
      api(`/api/v1/create-profile/${STAFF_ENDPOINTS[role]}/`, { method: 'POST', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['staff'] }),
  })
}

export function useSetStaffActive() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api<StaffMember>(`/api/v1/staff/${id}/${active ? 'activate' : 'deactivate'}/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['staff'] }),
  })
}

export function useResetStaffPassword() {
  return useMutation({
    mutationFn: (id: number) =>
      api<{ temporary_password: string }>(`/api/v1/staff/${id}/reset-password/`, { method: 'POST' }),
  })
}

export function useDepartments() {
  return useQuery({
    queryKey: ['departments'],
    queryFn: () => api<Page<Department>>('/api/v1/departments/', { query: { page_size: 100 } }),
    select: (page) => page.results,
  })
}

export function useSaveDepartment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...input }: Partial<Department>) =>
      api<Department>(id ? `/api/v1/departments/${id}/` : '/api/v1/departments/', {
        method: id ? 'PATCH' : 'POST',
        body: input,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['departments'] }),
  })
}

export function useSaveHospitalSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: Partial<Hospital>) => api<Hospital>('/api/v1/hospital/', { method: 'PATCH', body: input }),
    onSuccess: (hospital) => queryClient.setQueryData(['hospital'], hospital),
  })
}

// ---- Reports ----

export type ReportName = 'clinical' | 'financial' | 'pharmacy' | 'lab'

export interface ClinicalReport {
  visits: {
    total: number
    by_status: Record<string, number>
    by_triage: Record<string, number>
    per_day: { day: string; visits: number }[]
    per_doctor: { doctor_id: number; doctor: string; visits: number; completed: number }[]
    average_wait_minutes: number | null
    average_consultation_minutes: number | null
  }
  new_patients: number
  top_diagnoses: { code: string; title: string; count: number }[]
  uncoded_diagnoses: number
}

export interface FinancialReport {
  collected: {
    total: string
    from_patients: string
    from_insurers: string
    by_method: Record<string, string>
    per_day: { day: string; total: string }[]
  }
  charged: { total: string; by_category: Record<string, string> }
  receivables: { patients: string; insurers: string; invoices: number; aging_days: Record<string, string> }
  insurance_outstanding?: Record<string, { total: string; by_status: Record<string, { count: number; amount: string }> }>
}

export interface PharmacyReport {
  top_dispensed: { drug_id: number; drug__name: string; quantity: number; times: number }[]
  low_stock: { id: number; name: string; quantity_in_stock: number; reorder_level: number }[]
  stock_value: string
  drugs_without_price: number
}

export interface LabReport {
  tests: number
  by_status: Record<string, number>
  by_test: { test__name: string; count: number; completed: number }[]
  average_turnaround_hours: number | null
  pending_now: number
}

export function useReport<T>(name: ReportName, period: { date_from: string; date_to: string }, enabled = true) {
  return useQuery({
    queryKey: ['report', name, period],
    queryFn: () => api<T>(`/api/v1/reports/${name}/`, { query: period }),
    enabled,
  })
}
