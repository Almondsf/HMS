'''Appointment booking rules.'''

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit import events
from clinical import services as clinical_services
from profiles.models import DoctorProfile, PatientProfile

from .models import Appointment

MIN_DURATION, MAX_DURATION = 5, 240


def _check_slot(*, patient, doctor, starts_at, duration_minutes, exclude=None):
    '''
    Validate a slot and return its end time. The doctor's and patient's rows
    are locked first, so concurrent bookings for either are serialised and
    can never both pass the overlap check.
    '''
    if not MIN_DURATION <= duration_minutes <= MAX_DURATION:
        raise ValidationError({'duration_minutes': f'Must be between {MIN_DURATION} and {MAX_DURATION} minutes.'})
    if starts_at <= timezone.now():
        raise ValidationError({'starts_at': 'Appointments must be in the future.'})
    if not doctor.user.is_active:
        raise ValidationError({'doctor': 'This doctor is no longer active.'})
    if not patient.user.is_active:
        raise ValidationError({'patient': "This patient's record is deactivated."})

    DoctorProfile.objects.select_for_update().filter(pk=doctor.pk).first()
    PatientProfile.objects.select_for_update().filter(pk=patient.pk).first()

    ends_at = starts_at + timedelta(minutes=duration_minutes)
    overlapping = Appointment.objects.filter(
        status__in=Appointment.ACTIVE_STATUSES, starts_at__lt=ends_at, ends_at__gt=starts_at
    )
    if exclude is not None:
        overlapping = overlapping.exclude(pk=exclude.pk)
    if overlapping.filter(doctor=doctor).exists():
        raise ValidationError({'starts_at': f'Dr {doctor.user.get_full_name()} already has an appointment then.'})
    if overlapping.filter(patient=patient).exists():
        raise ValidationError({'starts_at': 'This patient already has an appointment then.'})
    return ends_at


@transaction.atomic
def book_appointment(*, patient, doctor, starts_at, duration_minutes=15, reason='', department=None, booked_by=None):
    ends_at = _check_slot(patient=patient, doctor=doctor, starts_at=starts_at, duration_minutes=duration_minutes)
    appointment = Appointment.objects.create(
        patient=patient,
        doctor=doctor,
        department=department,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
        booked_by=booked_by,
    )
    events.publish('scheduling.appointment_booked', resource=appointment, starts_at=starts_at, doctor_id=doctor.pk)
    return appointment


def _require_scheduled(appointment, verb):
    if appointment.status != Appointment.Status.SCHEDULED:
        raise ValidationError(
            f'Only scheduled appointments can be {verb} (this one is {appointment.get_status_display()}).'
        )


@transaction.atomic
def reschedule_appointment(*, appointment, starts_at=None, duration_minutes=None):
    _require_scheduled(appointment, 'rescheduled')
    starts_at = starts_at or appointment.starts_at
    duration_minutes = duration_minutes or appointment.duration_minutes
    appointment.ends_at = _check_slot(
        patient=appointment.patient,
        doctor=appointment.doctor,
        starts_at=starts_at,
        duration_minutes=duration_minutes,
        exclude=appointment,
    )
    appointment.starts_at = starts_at
    appointment.save(update_fields=['starts_at', 'ends_at', 'updated_at'])
    events.publish('scheduling.appointment_rescheduled', resource=appointment, starts_at=starts_at)
    return appointment


@transaction.atomic
def cancel_appointment(*, appointment, reason=''):
    _require_scheduled(appointment, 'cancelled')
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancellation_reason = reason
    appointment.save(update_fields=['status', 'cancellation_reason', 'updated_at'])
    events.publish('scheduling.appointment_cancelled', resource=appointment)
    return appointment


@transaction.atomic
def mark_no_show(*, appointment):
    _require_scheduled(appointment, 'marked as no-show')
    if appointment.starts_at > timezone.now():
        raise ValidationError("An appointment can't be a no-show before its start time.")
    appointment.status = Appointment.Status.NO_SHOW
    appointment.save(update_fields=['status', 'updated_at'])
    events.publish('scheduling.appointment_no_show', resource=appointment)
    return appointment


@transaction.atomic
def check_in(*, appointment):
    '''The patient has arrived: open a visit, which puts them in the doctor's queue.'''
    _require_scheduled(appointment, 'checked in')
    if timezone.localdate(appointment.starts_at) != timezone.localdate():
        raise ValidationError('Patients can only be checked in on the day of their appointment.')
    appointment.visit = clinical_services.open_visit(
        patient=appointment.patient,
        assigned_doctor=appointment.doctor,
        reason_for_visit=appointment.reason or 'Scheduled appointment',
    )
    appointment.status = Appointment.Status.CHECKED_IN
    appointment.save(update_fields=['visit', 'status', 'updated_at'])
    events.publish('scheduling.patient_checked_in', resource=appointment, visit_id=appointment.visit_id)
    return appointment
