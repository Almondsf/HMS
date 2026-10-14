'''Clinical workflow: recording consultations and what comes out of them.'''

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit import events
from lab import services as lab_services
from tenants.features import Feature, has_feature

from . import vitals as vitals_rules
from .models import Consultation, Diagnosis, Prescription, Visit, VitalSigns


@transaction.atomic
def record_consultation(*, doctor_user, visit, prescriptions=(), diagnoses=(), lab_tests=(), lab_reason='', **notes):
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

    if visit.status == Visit.Status.WAITING:
        _set_status(visit, Visit.Status.IN_PROGRESS, 'clinical.visit_started')

    consultation = Consultation.objects.create(visit=visit, **notes)

    for item in prescriptions:
        add_prescription(consultation=consultation, **item)

    for item in diagnoses:
        add_diagnosis(consultation=consultation, by=doctor_user, **item)

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


def open_visit(*, patient, assigned_doctor, reason_for_visit):
    '''A patient arrives (walk-in or checked-in appointment) and joins the doctor's queue.'''
    visit = Visit.objects.create(patient=patient, assigned_doctor=assigned_doctor, reason_for_visit=reason_for_visit)
    events.publish('clinical.visit_opened', resource=visit, doctor_id=visit.assigned_doctor_id)
    return visit


def _set_status(visit, status, event):
    visit.status = status
    visit.save(update_fields=['status', 'updated_at'])
    events.publish(event, resource=visit)
    return visit


def _require_assigned_doctor(visit, user):
    if not (user.is_superuser or visit.assigned_doctor.user_id == user.id):
        raise PermissionDenied("Only the visit's assigned doctor can do this.")


@transaction.atomic
def start_visit(*, visit, by):
    '''The doctor calls the patient in.'''
    _require_assigned_doctor(visit, by)
    if visit.status != Visit.Status.WAITING:
        raise ValidationError(f'Only waiting visits can be started (this one is {visit.get_status_display()}).')
    return _set_status(visit, Visit.Status.IN_PROGRESS, 'clinical.visit_started')


@transaction.atomic
def complete_visit(*, visit, by):
    _require_assigned_doctor(visit, by)
    if visit.status not in (Visit.Status.WAITING, Visit.Status.IN_PROGRESS):
        raise ValidationError(f'This visit is already {visit.get_status_display().lower()}.')
    return _set_status(visit, Visit.Status.COMPLETED, 'clinical.visit_completed')


@transaction.atomic
def cancel_visit(*, visit):
    '''Front desk removes a patient who left before being seen.'''
    if visit.status != Visit.Status.WAITING:
        raise ValidationError('Only visits still waiting can be cancelled.')
    return _set_status(visit, Visit.Status.CANCELLED, 'clinical.visit_cancelled')


def add_prescription(*, consultation, drug=None, medication_name='', **fields):
    if not (drug or medication_name):
        raise ValidationError({'medication_name': 'Choose a drug or enter a medication name.'})
    return Prescription.objects.create(
        consultation=consultation,
        drug=drug,
        medication_name=medication_name or drug.name,
        **fields,
    )


@transaction.atomic
def record_vitals(*, visit, by, **readings):
    '''Record observations; critical values raise a domain event (e.g. to alert the doctor).'''
    if visit.status == Visit.Status.CANCELLED:
        raise ValidationError({'visit': 'This visit was cancelled.'})
    if not any(readings.get(field) is not None for field in vitals_rules.MEASUREMENTS):
        raise ValidationError('Record at least one measurement.')
    errors = vitals_rules.implausible(readings)
    if errors:
        raise ValidationError(errors)

    vitals = VitalSigns.objects.create(visit=visit, recorded_by=by, **readings)
    flags, critical = vitals_rules.assess(readings)
    if critical:
        events.publish('clinical.critical_vitals', resource=vitals, flags=flags, visit_id=visit.pk)
    return vitals


@transaction.atomic
def triage(*, visit, by, level, notes=''):
    if visit.status not in Visit.QUEUE_STATUSES:
        raise ValidationError('Only patients still in the queue can be triaged.')
    visit.triage_level, visit.triage_notes = level, notes
    visit.triaged_at, visit.triaged_by = timezone.now(), by
    visit.save(update_fields=['triage_level', 'triage_notes', 'triaged_at', 'triaged_by', 'updated_at'])
    events.publish('clinical.patient_triaged', resource=visit, level=level)
    if level == Visit.Triage.EMERGENCY:
        events.publish('clinical.emergency_arrival', resource=visit, doctor_id=visit.assigned_doctor_id)
    return visit


def _check_diagnosis(*, consultation, code, description, kind, certainty, exclude=None):
    if code is None and not description:
        raise ValidationError({'code': 'Choose an ICD-10 code or describe the diagnosis.'})
    if code is not None and not code.is_active:
        raise ValidationError({'code': f'{code.code} is a retired code.'})
    if kind == Diagnosis.Kind.PRIMARY and certainty != Diagnosis.Certainty.RULED_OUT:
        others = consultation.diagnoses.filter(kind=Diagnosis.Kind.PRIMARY).exclude(
            certainty=Diagnosis.Certainty.RULED_OUT
        )
        if exclude is not None:
            others = others.exclude(pk=exclude.pk)
        if others.exists():
            raise ValidationError({'kind': 'This consultation already has a primary diagnosis.'})


@transaction.atomic
def add_diagnosis(*, consultation, by, code=None, description='', kind=Diagnosis.Kind.PRIMARY, certainty=None):
    _require_assigned_doctor(consultation.visit, by)
    certainty = certainty or Diagnosis.Certainty.PROVISIONAL
    _check_diagnosis(consultation=consultation, code=code, description=description, kind=kind, certainty=certainty)
    diagnosis = Diagnosis.objects.create(
        consultation=consultation,
        code=code,
        description=description or code.title,
        kind=kind,
        certainty=certainty,
    )
    events.publish('clinical.diagnosis_recorded', resource=diagnosis, code=diagnosis.code_id, certainty=certainty)
    return diagnosis


@transaction.atomic
def update_diagnosis(*, diagnosis, by, **changes):
    """E.g. confirm a provisional diagnosis once lab results are in, or rule it out."""
    _require_assigned_doctor(diagnosis.consultation.visit, by)
    proposed = {
        field: changes.get(field, getattr(diagnosis, field)) for field in ('code', 'description', 'kind', 'certainty')
    }
    _check_diagnosis(consultation=diagnosis.consultation, exclude=diagnosis, **proposed)
    if 'code' in changes and 'description' not in changes and proposed['code'] is not None:
        proposed['description'] = proposed['code'].title
    for field, value in proposed.items():
        setattr(diagnosis, field, value)
    diagnosis.save()
    if 'certainty' in changes:
        events.publish('clinical.diagnosis_updated', resource=diagnosis, certainty=diagnosis.certainty)
    return diagnosis
