/** Patients, staff, appointments, visits and the queue. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type Page } from '@/lib/api'

// ---- Types (mirror the API) ----

export interface PatientUser {
  id: number
  email: string | null
  first_name: string
  last_name: string
  gender: 'male' | 'female' | 'other' | null
  date_of_birth: string | null
  phone_number: string | null
  address: string | null
  emergency_contact: string | null
  emergency_phone: string | null
}

export interface Patient {
  id: number
  mrn: string
  user: PatientUser
  blood_group: string | null
  genotype: string | null
  allergies: string | null
  medical_history: string | null
  assigned_doctor: number | null
}

export type PatientInput = {
  mrn?: string
  user: Partial<Omit<PatientUser, 'id'>> & { first_name: string; last_name: string }
  blood_group?: string | null
  genotype?: string | null
  allergies?: string
  medical_history?: string
}

export interface StaffMember {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  role: string
  phone_number: string | null
  department: { id: number; name: string } | null
  specialty: string | null
  doctor_id: number | null
  is_active: boolean
}

export type AppointmentStatus = 'scheduled' | 'checked_in' | 'cancelled' | 'no_show'

export interface Appointment {
  id: number
  patient: number
  patient_name: string
  patient_mrn: string
  doctor: number
  doctor_name: string
  starts_at: string
  ends_at: string
  duration_minutes: number
  reason: string
  status: AppointmentStatus
  cancellation_reason: string
  visit: number | null
}

export type TriageLevel = 'emergency' | 'urgent' | 'standard' | 'non_urgent'

export interface QueueEntry {
  id: number
  position: number | null
  status: 'waiting' | 'in_progress'
  triage_level: TriageLevel | ''
  patient: { id: number; mrn: string; name: string }
  doctor: { id: number; name: string }
  reason_for_visit: string
  visit_date: string
  waiting_minutes: number
  appointment_time: string | null
}

export function fullName(user: { first_name: string; last_name: string }): string {
  return `${user.first_name} ${user.last_name}`.trim()
}

// ---- Patients ----

export function usePatients(search: string, page = 1) {
  return useQuery({
    queryKey: ['patients', search, page],
    queryFn: () => api<Page<Patient>>('/api/v1/patients/', { query: { search, page } }),
    placeholderData: (previous) => previous,
  })
}

export function usePatient(id: number | undefined) {
  return useQuery({
    queryKey: ['patient', id],
    queryFn: () => api<Patient>(`/api/v1/patients/${id}/`),
    enabled: id !== undefined,
  })
}

export function useSavePatient(id?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PatientInput) =>
      api<Patient>(id ? `/api/v1/patients/${id}/` : '/api/v1/patients/', {
        method: id ? 'PATCH' : 'POST',
        body: input,
      }),
    onSuccess: (patient) => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      queryClient.setQueryData(['patient', patient.id], patient)
    },
  })
}

// ---- Staff ----

export function useDoctors() {
  return useQuery({
    queryKey: ['staff', 'doctors'],
    queryFn: () =>
      api<Page<StaffMember>>('/api/v1/staff/', { query: { role: 'doctor', is_active: true, page_size: 100 } }),
    select: (page) => page.results,
    staleTime: 5 * 60_000,
  })
}

// ---- Appointments ----

export function useAppointments(filters: { date: string; doctor?: number | '' }) {
  return useQuery({
    queryKey: ['appointments', filters],
    queryFn: () =>
      api<Page<Appointment>>('/api/v1/appointments/', {
        query: { date: filters.date, doctor: filters.doctor, ordering: 'starts_at', page_size: 100 },
      }),
    select: (page) => page.results,
  })
}

export interface BookingInput {
  patient: number
  doctor: number
  starts_at: string
  duration_minutes: number
  reason: string
}

function useAppointmentMutation<TInput>(mutationFn: (input: TInput) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

export function useBookAppointment() {
  return useAppointmentMutation((input: BookingInput) =>
    api<Appointment>('/api/v1/appointments/', { method: 'POST', body: input }),
  )
}

export function useAppointmentAction() {
  return useAppointmentMutation(
    ({ id, action, reason }: { id: number; action: 'check-in' | 'cancel' | 'no-show'; reason?: string }) =>
      api<Appointment>(`/api/v1/appointments/${id}/${action}/`, {
        method: 'POST',
        body: action === 'cancel' ? { reason: reason ?? '' } : {},
      }),
  )
}

// ---- Visits & queue ----

export function useOpenVisit() {
  return useAppointmentMutation((input: { patient: number; assigned_doctor: number; reason_for_visit: string }) =>
    api('/api/v1/visits/', { method: 'POST', body: input }),
  )
}

export function useCancelVisit() {
  return useAppointmentMutation((visitId: number) => api(`/api/v1/visits/${visitId}/cancel/`, { method: 'POST' }))
}

export function useQueue(doctor?: number | '') {
  return useQuery({
    queryKey: ['queue', doctor],
    queryFn: () => api<QueueEntry[]>('/api/v1/queue/', { query: { doctor } }),
    refetchInterval: 15_000, // live board
  })
}
