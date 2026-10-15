import type { HospitalState } from '@/api/platform'
import { Badge } from '@/components/ui'
import { formatMoney } from '@/lib/hospital'

export const STATE_LABELS: Record<HospitalState, string> = {
  trialing: 'On trial',
  paying: 'Paying',
  overdue: 'Overdue',
  lapsed: 'Lapsed (read-only)',
  suspended: 'Suspended',
}

export const STATE_TONES = {
  trialing: 'brand',
  paying: 'green',
  overdue: 'amber',
  lapsed: 'red',
  suspended: 'gray',
} as const satisfies Record<HospitalState, string>

export function StateBadge({ state }: { state: HospitalState }) {
  return <Badge tone={STATE_TONES[state]}>{STATE_LABELS[state]}</Badge>
}

/** Platform prices are in naira. */
export const naira = (amount: string | number) => formatMoney(amount, 'NGN').replace(/\.00$/, '')
