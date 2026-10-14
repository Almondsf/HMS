/** Lab orders and results, the test catalogue, the drug list and dispensing. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type Page } from '@/lib/api'

// ---- Lab ----

export type ResultStatus = 'pending' | 'collected' | 'in_progress' | 'completed' | 'cancelled'
export type OrderStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled'

export interface TestResult {
  id: number
  order: number
  test: number
  test_name: string
  normal_range: string | null
  status: ResultStatus
  result_value: string
  notes: string | null
  labtech_name: string | null
  completed_at: string | null
}

export interface TestOrder {
  id: number
  patient: number
  patient_name: string
  consultation: number | null
  ordered_by_name: string | null
  reason: string
  status: OrderStatus
  ordered_at: string
  results: TestResult[]
}

export interface LabTestItem {
  id: number
  name: string
  description: string | null
  normal_range: string | null
  cost: string
  is_active: boolean
}

export function useLabOrders(status: OrderStatus) {
  return useQuery({
    queryKey: ['lab-orders', status],
    queryFn: () =>
      api<Page<TestOrder>>('/api/v1/lab/test-orders/', {
        query: { status, ordering: status === 'completed' ? '-ordered_at' : 'ordered_at', page_size: 50 },
      }),
    select: (page) => page.results,
    refetchInterval: 30_000,
  })
}

export function useLabOrder(id: number) {
  return useQuery({ queryKey: ['lab-order', id], queryFn: () => api<TestOrder>(`/api/v1/lab/test-orders/${id}/`) })
}

export function useUpdateResult() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: number; status?: ResultStatus; result_value?: string; notes?: string }) =>
      api<TestResult>(`/api/v1/lab/test-results/${id}/`, { method: 'PATCH', body: changes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lab-orders'] })
      queryClient.invalidateQueries({ queryKey: ['lab-order'] })
    },
  })
}

export function usePlaceLabOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { patient: number; tests: number[]; reason: string }) =>
      api<TestOrder>('/api/v1/lab/test-orders/', { method: 'POST', body: input }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['lab-orders'] }),
  })
}

export function useLabTests() {
  return useQuery({
    queryKey: ['lab-tests', 'all'],
    queryFn: () => api<Page<LabTestItem>>('/api/v1/lab/tests/', { query: { page_size: 100, ordering: 'name' } }),
    select: (page) => page.results,
  })
}

export function useSaveLabTest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...input }: Partial<LabTestItem>) =>
      api<LabTestItem>(id ? `/api/v1/lab/tests/${id}/` : '/api/v1/lab/tests/', {
        method: id ? 'PATCH' : 'POST',
        body: input,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['lab-tests'] }),
  })
}

// ---- Pharmacy ----

export interface PendingPrescription {
  id: number
  consultation: number
  patient: number
  patient_name: string
  prescribed_by: string
  drug: number | null
  medication_name: string
  dosage: string
  frequency: string
  duration: string
  quantity: number | null
  quantity_dispensed: number
  instructions: string | null
  created_at: string
}

export interface DrugItem {
  id: number
  name: string
  description: string | null
  unit: string
  quantity_in_stock: number
  reorder_level: number
  unit_price: string | null
  is_low_stock: boolean
}

export function usePendingPrescriptions() {
  return useQuery({
    queryKey: ['prescriptions', 'pending'],
    queryFn: () =>
      api<Page<PendingPrescription>>('/api/v1/prescriptions/', {
        query: { pending: true, ordering: 'created_at', page_size: 100 },
      }),
    select: (page) => page.results,
    refetchInterval: 30_000,
  })
}

export function useDrugs(filters: { name?: string; low_stock?: boolean }) {
  return useQuery({
    queryKey: ['drugs', 'list', filters],
    queryFn: () =>
      api<Page<DrugItem>>('/api/v1/pharmacy/drugs/', {
        query: { name: filters.name, low_stock: filters.low_stock || undefined, page_size: 100, ordering: 'name' },
      }),
    select: (page) => page.results,
  })
}

export function useSaveDrug() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...input }: Partial<DrugItem>) =>
      api<DrugItem>(id ? `/api/v1/pharmacy/drugs/${id}/` : '/api/v1/pharmacy/drugs/', {
        method: id ? 'PATCH' : 'POST',
        body: input,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['drugs'] }),
  })
}

export interface DispenseItemInput {
  prescription: number
  drug: number
  quantity_dispensed: number
  notes?: string
}

export function useDispense() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (items: DispenseItemInput[]) =>
      api('/api/v1/pharmacy/dispense-transactions/', { method: 'POST', body: { items } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prescriptions'] })
      queryClient.invalidateQueries({ queryKey: ['drugs'] })
    },
  })
}
