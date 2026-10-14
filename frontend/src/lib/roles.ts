export type Role =
  | 'admin'
  | 'doctor'
  | 'nurse'
  | 'receptionist'
  | 'pharmacist'
  | 'lab_tech'
  | 'cashier'
  | 'patient'

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrator',
  doctor: 'Doctor',
  nurse: 'Nurse',
  receptionist: 'Front desk',
  pharmacist: 'Pharmacist',
  lab_tech: 'Lab technician',
  cashier: 'Cashier',
  patient: 'Patient',
}

/** Modules a hospital's plan can include (GET /api/v1/hospital/ -> features). */
export type Feature = 'clinical' | 'pharmacy' | 'lab' | 'billing' | 'insurance'
