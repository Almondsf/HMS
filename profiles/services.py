'''Patient and staff records: numbering, registration, deactivation.'''

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction

from authentication import services as auth_services

from .models import PatientProfile, RecordSequence


@transaction.atomic
def next_record_number(name, prefix):
    '''
    Next number from a per-hospital counter, e.g. MRN-000124. The counter row
    is locked, so concurrent registrations never get the same number.
    '''
    try:
        with transaction.atomic():
            sequence, _ = RecordSequence.objects.select_for_update().get_or_create(name=name)
    except IntegrityError:  # another request created the counter at the same moment
        sequence = RecordSequence.objects.select_for_update().get(name=name)
    sequence.last_value += 1
    sequence.save(update_fields=['last_value'])
    return f'{prefix}-{sequence.last_value:06d}'


def next_mrn():
    prefix = getattr(connection.tenant, 'mrn_prefix', None) or 'MRN'
    while True:
        # Skip numbers already taken by records imported with their existing MRN
        mrn = next_record_number('mrn', prefix)
        if not PatientProfile.objects.filter(mrn=mrn).exists():
            return mrn


def set_staff_active(*, staff_user, active, by):
    '''Deactivate (or reactivate) a staff account. Deactivation signs them out everywhere.'''
    if staff_user.pk == by.pk:
        raise PermissionDenied("You can't change your own account's status.")
    staff_user.is_active = active
    staff_user.save(update_fields=['is_active'])
    if not active:
        auth_services.revoke_all_sessions(staff_user)
    return staff_user
