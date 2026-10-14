from io import StringIO

from django.core.management import call_command

from audit.models import AuditEvent
from authentication.models import User
from helpers.testing import TenantAPITestCase, make_user


class RevokePatientPrivilegesTests(TenantAPITestCase):
    def test_patients_lose_admin_rights_and_staff_keep_theirs(self):
        patient = make_user(User.UserType.PATIENT)
        User.objects.filter(pk=patient.pk).update(is_superuser=True, is_staff=True, is_admin=True)
        admin = make_user(User.UserType.ADMIN)
        User.objects.filter(pk=admin.pk).update(is_superuser=True)

        call_command('revoke_patient_privileges', '--dry-run', stdout=StringIO())
        patient.refresh_from_db()
        self.assertTrue(patient.is_superuser)  # dry run changes nothing

        call_command('revoke_patient_privileges', stdout=StringIO())
        patient.refresh_from_db()
        admin.refresh_from_db()
        self.assertFalse(patient.is_superuser or patient.is_staff or patient.is_admin)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(AuditEvent.objects.filter(action='privileges_revoked', actor_id=patient.pk).exists())
