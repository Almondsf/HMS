'''Lab workflow: placing orders and recording results.'''

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import TestOrder, TestResult


@transaction.atomic
def place_order(*, patient, tests, ordered_by=None, consultation=None, reason=''):
    '''Create an order with one pending result per requested test.'''
    if not tests:
        raise ValidationError({'tests': 'Order at least one test.'})
    if consultation and consultation.visit.patient_id != patient.id:
        raise ValidationError({'patient': "Patient doesn't match the consultation."})
    retired = [test.name for test in tests if not test.is_active]
    if retired:
        raise ValidationError({'tests': f"No longer offered: {', '.join(retired)}"})

    order = TestOrder.objects.create(
        patient=patient, consultation=consultation, ordered_by=ordered_by, reason=reason
    )
    for test in tests:
        TestResult.objects.create(order=order, test=test)
    return order


@transaction.atomic
def record_result(*, result, labtech_user, **changes):
    '''
    Update a result (status, result_value, notes). Completed or cancelled
    results are final; corrections need a formal amendment flow.
    '''
    labtech = getattr(labtech_user, 'labtechprofile', None)
    if labtech is None:
        raise PermissionDenied('Only lab technicians can record results.')

    result = TestResult.objects.select_for_update().get(pk=result.pk)
    if result.status in TestResult.FINAL_STATUSES:
        raise ValidationError(f'This result is already {result.get_status_display().lower()} and cannot be changed.')

    for field in ('status', 'result_value', 'notes'):
        if field in changes:
            setattr(result, field, changes[field])

    if result.status == TestResult.Status.COMPLETED:
        if not result.result_value:
            raise ValidationError({'result_value': 'A completed result needs a value.'})
        result.completed_at = timezone.now()
    result.labtech = labtech
    result.save()

    _sync_order_status(result.order)
    return result


def _sync_order_status(order):
    '''An order's status follows its results.'''
    Status = TestResult.Status
    statuses = set(order.results.values_list('status', flat=True))

    if statuses == {Status.CANCELLED}:
        new_status = TestOrder.Status.CANCELLED
    elif statuses <= set(TestResult.FINAL_STATUSES):
        new_status = TestOrder.Status.COMPLETED
    elif statuses == {Status.PENDING}:
        new_status = TestOrder.Status.PENDING
    else:
        new_status = TestOrder.Status.IN_PROGRESS

    if order.status != new_status:
        order.status = new_status
        order.save(update_fields=['status'])
    return order
