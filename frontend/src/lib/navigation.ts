import {
  CalendarDays,
  CreditCard,
  FlaskConical,
  LayoutDashboard,
  ListOrdered,
  Pill,
  ShieldCheck,
  Users,
  type LucideIcon,
} from 'lucide-react'

import type { Feature, Role } from './roles'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Who sees the item; omit for everyone signed in. */
  roles?: Role[]
  /** Module the hospital's plan must include. */
  feature?: Feature
}

/** Who may open each screen: shared by the sidebar and the routes (the API enforces it too). */
export const ACCESS = {
  queue: ['receptionist', 'admin', 'nurse', 'doctor'],
  appointments: ['receptionist', 'admin', 'nurse', 'doctor'],
  patients: ['receptionist', 'admin', 'nurse', 'doctor', 'lab_tech', 'pharmacist'],
  visits: ['doctor', 'nurse', 'admin'],
  lab: ['lab_tech', 'admin'],
  pharmacy: ['pharmacist', 'admin'],
  billing: ['cashier', 'admin', 'receptionist'],
  billingOffice: ['cashier', 'admin'],
} satisfies Record<string, Role[]>

/** Sidebar entries. Each screen chunk adds its items here. */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  {
    to: '/queue',
    label: 'Queue',
    icon: ListOrdered,
    roles: ACCESS.queue,
    feature: 'clinical',
  },
  {
    to: '/appointments',
    label: 'Appointments',
    icon: CalendarDays,
    roles: ACCESS.appointments,
    feature: 'clinical',
  },
  {
    to: '/patients',
    label: 'Patients',
    icon: Users,
    roles: ACCESS.patients,
    feature: 'clinical',
  },
  { to: '/lab', label: 'Lab work', icon: FlaskConical, roles: ACCESS.lab, feature: 'lab' },
  { to: '/pharmacy', label: 'Pharmacy', icon: Pill, roles: ACCESS.pharmacy, feature: 'pharmacy' },
  { to: '/billing', label: 'Billing', icon: CreditCard, roles: ACCESS.billing, feature: 'billing' },
  {
    to: '/insurance/claims',
    label: 'Insurance claims',
    icon: ShieldCheck,
    roles: ACCESS.billingOffice,
    feature: 'insurance',
  },
]

export function visibleNavItems(role: Role, features: Feature[]): NavItem[] {
  return NAV_ITEMS.filter(
    (item) => (!item.roles || item.roles.includes(role)) && (!item.feature || features.includes(item.feature)),
  )
}
