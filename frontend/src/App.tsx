import { lazy, Suspense, type ComponentType, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router'

import { Spinner } from '@/components/ui'
import { AppLayout } from '@/layouts/AppLayout'
import { useAuth } from '@/lib/auth'
import { ACCESS } from '@/lib/navigation'
import type { Role } from '@/lib/roles'
import { currentHospital } from '@/lib/tenant'
import { DashboardPage } from '@/pages/DashboardPage'
import { LoginPage } from '@/pages/LoginPage'
import { ChangePasswordPage, ForgotPasswordPage, ResetPasswordPage } from '@/pages/PasswordPages'
import { NoHospitalPage, NotFoundPage } from '@/pages/StatusPages'

/** Load a screen only when first opened: smaller downloads on slow connections. */
function page<Module extends Record<string, unknown>>(load: () => Promise<Module>, name: keyof Module) {
  return lazy(async () => ({ default: (await load())[name] as ComponentType }))
}

const screens = {
  queue: page(() => import('@/pages/frontdesk/QueuePage'), 'QueuePage'),
  appointments: page(() => import('@/pages/frontdesk/AppointmentsPage'), 'AppointmentsPage'),
  patients: page(() => import('@/pages/frontdesk/PatientsPage'), 'PatientsPage'),
  patient: page(() => import('@/pages/frontdesk/PatientDetailPage'), 'PatientDetailPage'),
  visit: page(() => import('@/pages/clinical/VisitPage'), 'VisitPage'),
  lab: page(() => import('@/pages/lab/LabPage'), 'LabPage'),
  labTests: page(() => import('@/pages/lab/LabCataloguePage'), 'LabCataloguePage'),
  labPrint: page(() => import('@/pages/lab/LabPrintPage'), 'LabPrintPage'),
  pharmacy: page(() => import('@/pages/pharmacy/PharmacyPage'), 'PharmacyPage'),
  drugs: page(() => import('@/pages/pharmacy/DrugsPage'), 'DrugsPage'),
  billing: page(() => import('@/pages/billing/BillingPage'), 'BillingPage'),
  invoice: page(() => import('@/pages/billing/InvoicePage'), 'InvoicePage'),
  receipt: page(() => import('@/pages/billing/PrintPages'), 'ReceiptPage'),
  summary: page(() => import('@/pages/billing/SummaryPage'), 'SummaryPage'),
  claims: page(() => import('@/pages/billing/ClaimsPage'), 'ClaimsPage'),
  claimDocument: page(() => import('@/pages/billing/PrintPages'), 'ClaimDocumentPage'),
  reports: page(() => import('@/pages/admin/ReportsPage'), 'ReportsPage'),
  staff: page(() => import('@/pages/admin/StaffPage'), 'StaffPage'),
  departments: page(() => import('@/pages/admin/SetupPages'), 'DepartmentsPage'),
  tariff: page(() => import('@/pages/admin/SetupPages'), 'TariffPage'),
  insurers: page(() => import('@/pages/admin/SetupPages'), 'InsurersPage'),
  settings: page(() => import('@/pages/admin/SettingsPage'), 'SettingsPage'),
}

/** path -> [screen, who may open it] */
const ROUTES: [string, ComponentType, Role[]][] = [
  ['queue', screens.queue, ACCESS.queue],
  ['appointments', screens.appointments, ACCESS.appointments],
  ['patients', screens.patients, ACCESS.patients],
  ['patients/:id', screens.patient, ACCESS.patients],
  ['visits/:id', screens.visit, ACCESS.visits],
  ['lab', screens.lab, ACCESS.lab],
  ['lab/tests', screens.labTests, ACCESS.lab],
  ['lab/orders/:id/print', screens.labPrint, ACCESS.lab],
  ['pharmacy', screens.pharmacy, ACCESS.pharmacy],
  ['pharmacy/drugs', screens.drugs, ACCESS.pharmacy],
  ['billing', screens.billing, ACCESS.billing],
  ['billing/invoices/:id', screens.invoice, ACCESS.billing],
  ['billing/payments/:id/receipt', screens.receipt, ACCESS.billing],
  ['billing/summary', screens.summary, ACCESS.billingOffice],
  ['insurance/claims', screens.claims, ACCESS.billingOffice],
  ['insurance/claims/:id/document', screens.claimDocument, ACCESS.billingOffice],
  ['reports', screens.reports, ACCESS.reports],
  ['admin/staff', screens.staff, ACCESS.admin],
  ['admin/departments', screens.departments, ACCESS.admin],
  ['admin/fees', screens.tariff, ACCESS.admin],
  ['admin/insurers', screens.insurers, ACCESS.admin],
  ['admin/settings', screens.settings, ACCESS.admin],
]

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Restoring your session" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  // After an admin reset, nothing else opens until the temporary password is replaced
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  return children
}

/** Hide screens from roles that can't use them (the API enforces this too). */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.user_type)) return <NotFoundPage />
  return children
}

export function App() {
  if (!currentHospital()) return <NoHospitalPage />

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="change-password" element={<ChangePasswordPage />} />
        {ROUTES.map(([path, Screen, roles]) => (
          <Route
            key={path}
            path={path}
            element={
              <RequireRole roles={roles}>
                <Suspense fallback={<Spinner />}>
                  <Screen />
                </Suspense>
              </RequireRole>
            }
          />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
