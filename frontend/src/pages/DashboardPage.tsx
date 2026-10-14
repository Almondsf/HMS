import { Activity, CalendarDays, CreditCard, FlaskConical, Pill, Stethoscope, Users, type LucideIcon } from 'lucide-react'

import { Card, PageHeader } from '@/components/ui'
import { useCurrentUser } from '@/lib/auth'
import { useHospital } from '@/lib/hospital'
import type { Role } from '@/lib/roles'

interface Focus {
  icon: LucideIcon
  title: string
  description: string
}

/** What each role works on; becomes live links as the screens are added. */
const ROLE_FOCUS: Record<Role, Focus[]> = {
  admin: [
    { icon: Users, title: 'Staff & departments', description: 'Manage accounts and teams' },
    { icon: Activity, title: 'Reports', description: 'Clinical, financial and stock figures' },
  ],
  receptionist: [
    { icon: Users, title: 'Patients', description: 'Find or register patients' },
    { icon: CalendarDays, title: 'Appointments & queue', description: "Book, check in, see today's queue" },
  ],
  doctor: [{ icon: Stethoscope, title: 'My queue', description: 'Call in patients and record consultations' }],
  nurse: [{ icon: Activity, title: 'Triage & vitals', description: 'Prioritise the queue, record observations' }],
  lab_tech: [{ icon: FlaskConical, title: 'Lab work', description: 'Pending tests and results' }],
  pharmacist: [{ icon: Pill, title: 'Pharmacy queue', description: 'Prescriptions waiting to be dispensed' }],
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
        {ROLE_FOCUS[user.user_type].map(({ icon: Icon, title, description }) => (
          <Card key={title} className="p-5">
            <div className="mb-3 inline-flex rounded-lg bg-brand-50 p-2.5 text-brand-600">
              <Icon className="size-5" aria-hidden />
            </div>
            <p className="font-medium text-slate-900">{title}</p>
            <p className="mt-1 text-sm text-slate-500">{description}</p>
          </Card>
        ))}
      </div>
    </>
  )
}
