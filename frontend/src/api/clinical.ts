/** Visits, vitals, triage, consultations, diagnoses and the catalogues doctors pick from. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { TriageLevel } from '@/api/frontDesk'
import { api, type Page } from '@/lib/api'

export type VisitStatus = 'waiting' | 'in_progress' | 'completed' | 'cancelled'

export const VITAL_FIELDS = [
  { key: 'temperature_c', label: 'Temperature', unit: '°C', step: '0.1' },
  { key: 'pulse_bpm', label: 'Pulse', unit: 'bpm', step: '1' },
  { key: 'respiratory_rate', label: 'Breathing rate', unit: '/min', step: '1' },
  { key: 'systolic_bp', label: 'BP systolic', unit: 'mmHg', step: '1' },
  { key: 'diastolic_bp', label: 'BP diastolic', unit: 'mmHg', step: '1' },
  { key: 'spo2_percent', label: 'SpO₂', unit: '%', step: '1' },
  { key: 'weight_kg', label: 'Weight', unit: 'kg', step: '0.1' },
  { key: 'height_cm', label: 'Height', unit: 'cm', step: '0.1' },
  { key: 'blood_glucose_mmol', label: 'Blood glucose', unit: 'mmol/L', step: '0.1' },
  { key: 'pain_score', label: 'Pain (0–10)', unit: '', step: '1' },
] as const

export type VitalKey = (typeof VITAL_FIELDS)[number]['key']

export type Vitals = { [K in VitalKey]: string | number | null } & {
  id: number
  visit: number
  recorded_at: string
  recorded_by_name: string | null
  bmi: number | null
  flags: string[]
  is_critical: boolean
  notes: string
}

export interface Diagnosis {
  id: number
  code: string | null
  description: string
  kind: 'primary' | 'secondary'
  certainty: 'provisional' | 'confirmed' | 'ruled_out'
}

export interface Prescription {
  id: number
  drug: number | null
  medication_name: string
  dosage: string
  frequency: string
  duration: string
  quantity: number | null
  quantity_dispensed: number
  instructions: string | null
}

export interface LabResult {
  id: number
  test_name: string
  normal_range: string | null
  status: string
  result_value: string
  notes: string | null
}

export interface LabOrder {
  id: number
  status: string
  reason: string
  ordered_at: string
  results: LabResult[]
}

export interface Consultation {
  id: number
  visit: number
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  follow_up_date: string | null
  diagnoses: Diagnosis[]
  prescriptions: Prescription[]
  lab_orders: LabOrder[]
  created_at: string
}

export interface Visit {
  id: number
  patient: number
  assigned_doctor: number
  visit_date: string
  reason_for_visit: string
  status: VisitStatus
  triage_level: TriageLevel | ''
  triage_notes: string
  triaged_at: string | null
  vitals: Vitals[]
  consultations: Consultation[]
}

export interface IcdCode {
  code: string
  title: string
}

export interface Drug {
  id: number
  name: string
  unit: string
  quantity_in_stock: number
}

export interface LabTest {
  id: number
  name: string
  cost: string
}

export interface ConsultationInput {
  visit: number
  subjective: string
  objective: string
  assessment: string
  plan: string
  follow_up_date: string | null
  diagnoses: { code: string | null; description: string; kind: Diagnosis['kind']; certainty: Diagnosis['certainty'] }[]
  prescriptions: {
    drug: number | null
    medication_name: string
    dosage: string
    frequency: string
    duration: string
    quantity: number | null
    instructions: string
  }[]
  lab_tests: number[]
  lab_reason: string
}

// ---- Queries ----

export function useVisit(id: number) {
  return useQuery({ queryKey: ['visit', id], queryFn: () => api<Visit>(`/api/v1/visits/${id}/`) })
}

export function usePatientVisits(patientId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['visits', { patient: patientId }],
    queryFn: () =>
      api<Page<Visit>>('/api/v1/visits/', { query: { patient: patientId, ordering: '-visit_date', page_size: 20 } }),
    enabled,
    select: (page) => page.results,
  })
}

export function useIcdSearch(search: string) {
  return useQuery({
    queryKey: ['icd10', search],
    queryFn: () => api<Page<IcdCode>>('/api/v1/icd10/', { query: { search, page_size: 15 } }),
    enabled: search.trim().length >= 2,
    select: (page) => page.results,
    staleTime: 10 * 60_000,
  })
}

export function useDrugSearch(name: string) {
  return useQuery({
    queryKey: ['drugs', name],
    queryFn: () => api<Page<Drug>>('/api/v1/pharmacy/drugs/', { query: { name, page_size: 15 } }),
    enabled: name.trim().length >= 2,
    select: (page) => page.results,
  })
}

export function useLabCatalogue(enabled: boolean) {
  return useQuery({
    queryKey: ['lab-tests'],
    queryFn: () => api<Page<LabTest>>('/api/v1/lab/tests/', { query: { is_active: true, page_size: 100 } }),
    enabled,
    select: (page) => page.results,
    staleTime: 10 * 60_000,
  })
}

// ---- Mutations ----

function useVisitMutation<TInput, TResult>(visitId: number, mutationFn: (input: TInput) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['visit', visitId] })
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      queryClient.invalidateQueries({ queryKey: ['visits'] })
    },
  })
}

export function useVisitTransition(visitId: number) {
  return useVisitMutation(visitId, (action: 'start' | 'complete') =>
    api<Visit>(`/api/v1/visits/${visitId}/${action}/`, { method: 'POST' }),
  )
}

export function useTriage(visitId: number) {
  return useVisitMutation(visitId, (input: { triage_level: TriageLevel; triage_notes: string }) =>
    api<Visit>(`/api/v1/visits/${visitId}/triage/`, { method: 'POST', body: input }),
  )
}

export function useRecordVitals(visitId: number) {
  return useVisitMutation(visitId, (input: Partial<Record<VitalKey, string>> & { notes: string }) =>
    api<Vitals>('/api/v1/vitals/', { method: 'POST', body: { visit: visitId, ...input } }),
  )
}

export function useRecordConsultation(visitId: number) {
  return useVisitMutation(visitId, (input: ConsultationInput) =>
    api<Consultation>('/api/v1/consultations/', { method: 'POST', body: input }),
  )
}
