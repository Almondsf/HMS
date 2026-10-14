'''Clinical workflow: recording consultations and what comes out of them.'''

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit import events
from lab import services as lab_services
from tenants.features import Feature, has_feature

from .models import Consultation, Prescription, Visit


@transaction.atomic
def record_consultation(*, doctor_user, visit, prescriptions=(), lab_tests=(), lab_reason='', **notes):
    '''
    Record a consultation with its prescriptions and lab requests in one step.
    Only the visit's assigned doctor may do this.
    '''
    if visit.assigned_doctor.user_id != doctor_user.id:
        raise PermissionDenied('You can only record consultations for your assigned visits.')
    if visit.status == Visit.Status.CANCELLED:
        raise ValidationError({'visit': 'This visit was cancelled.'})
    if lab_tests and not has_feature(Feature.LAB):
        raise ValidationError({'lab_tests': "Your hospital's plan doesn't include the Laboratory module."})

    consultation = Consultation.objects.create(visit=visit, **notes)

    for item in prescriptions:
        add_prescription(consultation=consultation, **item)

    if lab_tests:
        lab_services.place_order(
            patient=visit.patient,
            consultation=consultation,
            ordered_by=visit.assigned_doctor,
            tests=lab_tests,
            reason=lab_reason,
        )

    events.publish('clinical.consultation_recorded', resource=consultation, visit_id=visit.pk)
    return consultation


def open_visit(serializer):
    '''Front desk opens a visit (queues the patient for the doctor).'''
    visit = serializer.save()
    events.publish('clinical.visit_opened', resource=visit, doctor_id=visit.assigned_doctor_id)
    return visit


def add_prescription(*, consultation, drug=None, medication_name='', **fields):
    if not (drug or medication_name):
        raise ValidationError({'medication_name': 'Choose a drug or enter a medication name.'})
    return Prescription.objects.create(
        consultation=consultation,
        drug=drug,
        medication_name=medication_name or drug.name,
        **fields,
    )
