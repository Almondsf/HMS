/** Invoices, payments, receipts, the tariff and insurance claims. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type Page } from '@/lib/api'

export type InvoiceStatus = 'draft' | 'issued' | 'paid' | 'void'
export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'mobile_money' | 'insurance'

export const PAYMENT_METHODS: { value: Exclude<PaymentMethod, 'insurance'>; label: string }[] = [
  { value: 'cash', label: 'Cash' },
  { value: 'card', label: 'Card / POS' },
  { value: 'transfer', label: 'Bank transfer' },
  { value: 'mobile_money', label: 'Mobile money' },
]

export interface InvoiceLine {
  id: number
  category: string
  description: string
  quantity: number
  unit_price: string
  amount: string
  needs_price: boolean
  voided: boolean
  void_reason: string
  added_by_name: string | null
  created_at: string
}

export interface Payment {
  id: number
  receipt_number: string
  invoice: number
  invoice_number: string
  amount: string
  method: PaymentMethod
  reference: string
  received_by_name: string | null
  voided: boolean
  void_reason: string
  created_at: string
}

export interface Invoice {
  id: number
  number: string
  patient: number
  patient_name: string
  patient_mrn: string
  visit: number | null
  status: InvoiceStatus
  subtotal: string
  discount: string
  discount_reason: string
  total: string
  amount_paid: string
  balance: string
  pending_insurance: string
  patient_due: string
  issued_at: string | null
  void_reason: string
  created_at: string
  lines: InvoiceLine[]
  payments: Payment[]
}

export interface ServiceItem {
  id: number
  code: string
  name: string
  category: string
  price: string
  charge_on: 'manual' | 'visit_opened' | 'consultation_recorded'
  is_active: boolean
}

export interface Receipt {
  hospital: { name: string; address: string; phone: string; email: string }
  receipt_number: string
  date: string
  patient: { name: string; mrn: string }
  invoice_number: string
  currency: string
  lines: InvoiceLine[]
  invoice_total: string
  amount_paid_now: string
  method: string
  reference: string
  balance_after: string
  received_by: string | null
  voided: boolean
}

export interface DailySummary {
  date: string
  payments: {
    count: number
    total: string
    by_method: Record<string, string>
    by_cashier: Record<string, { count: number; total: string }>
  }
  charges: { total: string; by_category: Record<string, string> }
  outstanding_invoices: number
}

// ---- Invoices ----

export function useInvoices(filters: { status?: InvoiceStatus; patient?: number }) {
  return useQuery({
    queryKey: ['invoices', filters],
    queryFn: () => api<Page<Invoice>>('/api/v1/billing/invoices/', { query: { ...filters, page_size: 50 } }),
    select: (page) => page.results,
  })
}

export function useInvoice(id: number) {
  return useQuery({ queryKey: ['invoice', id], queryFn: () => api<Invoice>(`/api/v1/billing/invoices/${id}/`) })
}

function useInvoiceMutation<TInput, TResult>(invoiceId: number, mutationFn: (input: TInput) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', invoiceId] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      queryClient.invalidateQueries({ queryKey: ['claims'] })
    },
  })
}

export function useInvoiceAction(invoiceId: number) {
  return useInvoiceMutation(invoiceId, ({ path, body }: { path: string; body?: object }) =>
    api<Invoice>(`/api/v1/billing/invoices/${invoiceId}/${path}`, { method: 'POST', body: body ?? {} }),
  )
}

export function useTakePayment(invoiceId: number) {
  return useInvoiceMutation(invoiceId, (input: { amount: string; method: PaymentMethod; reference: string }) =>
    api<Payment>('/api/v1/billing/payments/', { method: 'POST', body: { invoice: invoiceId, ...input } }),
  )
}

export function useVoidPayment(invoiceId: number) {
  return useInvoiceMutation(invoiceId, ({ id, reason }: { id: number; reason: string }) =>
    api<Payment>(`/api/v1/billing/payments/${id}/void/`, { method: 'POST', body: { reason } }),
  )
}

export function useReceipt(paymentId: number) {
  return useQuery({
    queryKey: ['receipt', paymentId],
    queryFn: () => api<Receipt>(`/api/v1/billing/payments/${paymentId}/receipt/`),
  })
}

export function useServiceItems(enabled = true) {
  return useQuery({
    queryKey: ['service-items'],
    queryFn: () => api<Page<ServiceItem>>('/api/v1/billing/services/', { query: { page_size: 100 } }),
    select: (page) => page.results,
    enabled,
  })
}

export function useSaveServiceItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...input }: Partial<ServiceItem>) =>
      api<ServiceItem>(id ? `/api/v1/billing/services/${id}/` : '/api/v1/billing/services/', {
        method: id ? 'PATCH' : 'POST',
        body: input,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['service-items'] }),
  })
}

export function useDailySummary(date: string) {
  return useQuery({
    queryKey: ['billing-summary', date],
    queryFn: () => api<DailySummary>('/api/v1/billing/summary/', { query: { date } }),
  })
}

// ---- Insurance ----

export type ClaimStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'paid'

export interface Provider {
  id: number
  name: string
  code: string
  kind: string
  default_coverage_percent: string
  requires_authorization: boolean
  is_active: boolean
}

export interface Coverage {
  id: number
  patient: number
  provider: number
  provider_name: string
  member_number: string
  plan_name: string
  coverage_percent: string | null
  effective_percent: string
  valid_from: string
  valid_to: string | null
  is_active: boolean
}

export interface Claim {
  id: number
  number: string
  invoice: number
  invoice_number: string
  patient_name: string
  coverage: number
  provider_name: string
  status: ClaimStatus
  claimed_amount: string
  approved_amount: string | null
  paid_amount: string
  authorization_code: string
  rejection_reason: string
  notes: string
  submitted_at: string | null
  responded_at: string | null
  paid_at: string | null
  created_at: string
}

export interface ClaimDocument {
  claim_number: string
  status: ClaimStatus
  provider: { name: string; code: string }
  member: {
    member_number: string
    plan: string
    name: string
    date_of_birth: string | null
    gender: string | null
    mrn: string
  }
  service_date: string
  attending_doctor: string | null
  authorization_code: string
  diagnoses: { code: string | null; description: string; kind: string; certainty: string }[]
  lines: { description: string; category: string; quantity: number; unit_price: string; amount: string }[]
  invoice_number: string
  invoice_total: string
  coverage_percent: string
  claimed_amount: string
}

export function useProviders() {
  return useQuery({
    queryKey: ['insurance-providers'],
    queryFn: () => api<Page<Provider>>('/api/v1/insurance/providers/', { query: { page_size: 100 } }),
    select: (page) => page.results,
    staleTime: 5 * 60_000,
  })
}

export function useSaveProvider() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...input }: Partial<Provider>) =>
      api<Provider>(id ? `/api/v1/insurance/providers/${id}/` : '/api/v1/insurance/providers/', {
        method: id ? 'PATCH' : 'POST',
        body: input,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['insurance-providers'] }),
  })
}

export function useCoverages(patientId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['coverages', patientId],
    queryFn: () => api<Page<Coverage>>('/api/v1/insurance/coverages/', { query: { patient: patientId } }),
    select: (page) => page.results,
    enabled,
  })
}

export function useAddCoverage(patientId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: Omit<Coverage, 'id' | 'patient' | 'provider_name' | 'effective_percent' | 'is_active'>) =>
      api<Coverage>('/api/v1/insurance/coverages/', { method: 'POST', body: { patient: patientId, ...input } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['coverages', patientId] }),
  })
}

export function useClaims(filters: { status?: ClaimStatus; invoice?: number }) {
  return useQuery({
    queryKey: ['claims', filters],
    queryFn: () => api<Page<Claim>>('/api/v1/insurance/claims/', { query: { ...filters, page_size: 50 } }),
    select: (page) => page.results,
  })
}

export function useCreateClaim(invoiceId: number) {
  return useInvoiceMutation(invoiceId, (input: { coverage: number; authorization_code: string }) =>
    api<Claim>('/api/v1/insurance/claims/', { method: 'POST', body: { invoice: invoiceId, ...input } }),
  )
}

export function useClaimAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action, body }: { id: number; action: 'submit' | 'respond' | 'pay'; body?: object }) =>
      api<Claim>(`/api/v1/insurance/claims/${id}/${action}/`, { method: 'POST', body: body ?? {} }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['claims'] })
      queryClient.invalidateQueries({ queryKey: ['invoice'] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })
}

export function useClaimDocument(id: number) {
  return useQuery({
    queryKey: ['claim-document', id],
    queryFn: () => api<ClaimDocument>(`/api/v1/insurance/claims/${id}/document/`),
  })
}
