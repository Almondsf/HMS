import type { TriageLevel } from '@/api/frontDesk'

export type Tone = 'brand' | 'gray' | 'green' | 'amber' | 'red'

export const TRIAGE: Record<TriageLevel, { label: string; tone: Tone }> = {
  emergency: { label: 'Emergency', tone: 'red' },
  urgent: { label: 'Urgent', tone: 'amber' },
  standard: { label: 'Standard', tone: 'brand' },
  non_urgent: { label: 'Non-urgent', tone: 'gray' },
}

export const VISIT_STATUS: Record<string, { label: string; tone: Tone }> = {
  waiting: { label: 'Waiting', tone: 'amber' },
  in_progress: { label: 'In consultation', tone: 'brand' },
  completed: { label: 'Completed', tone: 'green' },
  cancelled: { label: 'Cancelled', tone: 'gray' },
}
