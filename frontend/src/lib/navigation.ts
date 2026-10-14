import { LayoutDashboard, type LucideIcon } from 'lucide-react'

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

/** Sidebar entries. Each screen chunk adds its items here. */
export const NAV_ITEMS: NavItem[] = [{ to: '/', label: 'Dashboard', icon: LayoutDashboard }]

export function visibleNavItems(role: Role, features: Feature[]): NavItem[] {
  return NAV_ITEMS.filter(
    (item) => (!item.roles || item.roles.includes(role)) && (!item.feature || features.includes(item.feature)),
  )
}
