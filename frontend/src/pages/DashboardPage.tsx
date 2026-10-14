import { Activity, CalendarDays, CreditCard, FlaskConical, Pill, Stethoscope, Users, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'

import { Card, PageHeader } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { useHospital } from '@/lib/hospital'
import type { Role } from '@/lib/roles'

interface Focus {
  icon: LucideIcon
  title: string
  description: string
  /** Screen to open, once it exists. */
  to?: string
}

/** What each role works on; becomes live links as the screens are added. */
const ROLE_FOCUS: Record<Role, Focus[]> = {
  admin: [
    { icon: Users, title: 'Staff & departments', description: 'Manage accounts and teams' },
    { icon: Activity, title: 'Reports', description: 'Clinical, financial and stock figures' },
  ],
  receptionist: [
    { icon: Users, title: 'Patients', description: 'Find or register patients', to: '/patients' },
    { icon: CalendarDays, title: 'Appointments', description: 'Book and check in', to: '/appointments' },
    { icon: Activity, title: "Today's queue", description: 'Who is waiting for which doctor', to: '/queue' },
  ],
  doctor: [
    { icon: Stethoscope, title: 'My queue', description: 'Call in patients and record consultations', to: '/queue' },
    { icon: CalendarDays, title: 'My appointments', description: 'Your schedule', to: '/appointments' },
  ],
  nurse: [
    { icon: Activity, title: 'Triage & vitals', description: 'Prioritise the queue, record observations', to: '/queue' },
  ],
  lab_tech: [
    { icon: FlaskConical, title: 'Lab work', description: 'Pending tests and results', to: '/lab' },
    { icon: FlaskConical, title: 'Test list & prices', description: 'What the lab offers', to: '/lab/tests' },
  ],
  pharmacist: [
    { icon: Pill, title: 'Pharmacy queue', description: 'Prescriptions waiting to be dispensed', to: '/pharmacy' },
    { icon: Pill, title: 'Drugs & stock', description: 'Stock levels and prices', to: '/pharmacy/drugs' },
  ],
  cashier: [{ icon: CreditCard, title: 'Billing', description: 'Invoices, payments and receipts' }],
  patient: [{ icon: CalendarDays, title: 'My appointments', description: 'Upcoming visits and records' }],
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function DashboardPage() {
  const user = useCurrentUser()
  const { data: hospital } = useHospital()

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${user.first_name}`}
        description={hospital ? `${hospital.name} · ${hospital.plan} plan` : undefined}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {ROLE_FOCUS[user.user_type].map(({ icon: Icon, title, description, to }) => {
          const content = (
            <Card className={`h-full p-5 ${to ? 'transition-colors hover:border-brand-300 hover:bg-brand-50/40' : ''}`}>
              <div className="mb-3 inline-flex rounded-lg bg-brand-50 p-2.5 text-brand-600">
                <Icon className="size-5" aria-hidden />
              </div>
              <p className="font-medium text-slate-900">{title}</p>
              <p className="mt-1 text-sm text-slate-500">{description}</p>
            </Card>
          )
          return to ? (
            <Link key={title} to={to}>
              {content}
            </Link>
          ) : (
            <div key={title}>{content}</div>
          )
        })}
      </div>
    </>
  )
}
