import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router'

import { Spinner } from '@/components/ui'
import { AppLayout } from '@/layouts/AppLayout'
import { useAuth } from '@/lib/auth'
import { ACCESS } from '@/lib/navigation'
import type { Role } from '@/lib/roles'
import { currentHospital } from '@/lib/tenant'
import { VisitPage } from '@/pages/clinical/VisitPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { AppointmentsPage } from '@/pages/frontdesk/AppointmentsPage'
import { PatientDetailPage } from '@/pages/frontdesk/PatientDetailPage'
import { PatientsPage } from '@/pages/frontdesk/PatientsPage'
import { QueuePage } from '@/pages/frontdesk/QueuePage'
import { LabCataloguePage } from '@/pages/lab/LabCataloguePage'
import { LabPage } from '@/pages/lab/LabPage'
import { LabPrintPage } from '@/pages/lab/LabPrintPage'
import { LoginPage } from '@/pages/LoginPage'
import { DrugsPage } from '@/pages/pharmacy/DrugsPage'
import { PharmacyPage } from '@/pages/pharmacy/PharmacyPage'
import { NoHospitalPage, NotFoundPage } from '@/pages/StatusPages'

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Restoring your session" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
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
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route
          path="queue"
          element={
            <RequireRole roles={ACCESS.queue}>
              <QueuePage />
            </RequireRole>
          }
        />
        <Route
          path="appointments"
          element={
            <RequireRole roles={ACCESS.appointments}>
              <AppointmentsPage />
            </RequireRole>
          }
        />
        <Route
          path="patients"
          element={
            <RequireRole roles={ACCESS.patients}>
              <PatientsPage />
            </RequireRole>
          }
        />
        <Route
          path="patients/:id"
          element={
            <RequireRole roles={ACCESS.patients}>
              <PatientDetailPage />
            </RequireRole>
          }
        />
        <Route
          path="visits/:id"
          element={
            <RequireRole roles={ACCESS.visits}>
              <VisitPage />
            </RequireRole>
          }
        />
        <Route
          path="lab"
          element={
            <RequireRole roles={ACCESS.lab}>
              <LabPage />
            </RequireRole>
          }
        />
        <Route
          path="lab/tests"
          element={
            <RequireRole roles={ACCESS.lab}>
              <LabCataloguePage />
            </RequireRole>
          }
        />
        <Route
          path="lab/orders/:id/print"
          element={
            <RequireRole roles={ACCESS.lab}>
              <LabPrintPage />
            </RequireRole>
          }
        />
        <Route
          path="pharmacy"
          element={
            <RequireRole roles={ACCESS.pharmacy}>
              <PharmacyPage />
            </RequireRole>
          }
        />
        <Route
          path="pharmacy/drugs"
          element={
            <RequireRole roles={ACCESS.pharmacy}>
              <DrugsPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
