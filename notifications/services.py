'''
Appointment messages to patients: a confirmation when an appointment is
booked or moved, and a reminder the day before.

Each hospital switches them on in its settings. Nothing is sent to patients
who opted out or have no usable mobile number; those messages are recorded
as "not sent" with the reason, so the front desk can see what happened. A
monthly cap per hospital (SMS_MONTHLY_LIMIT_PER_HOSPITAL) bounds the cost.
'''

import logging
import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, connection, connections, transaction
from django.utils import timezone
from django_tenants.utils import tenant_context

from helpers import sms
from scheduling.models import Appointment
from tenants.models import Hospital

from .models import SmsMessage

logger = logging.getLogger('hms.sms')


def current_hospital():
    return Hospital.objects.get(pk=connection.tenant.pk)


def _when(moment, hospital):
    local = moment.astimezone(ZoneInfo(hospital.timezone))
    return f'{local:%a} {local.day} {local:%b}', f'{local:%H:%M}'  # "Tue 21 Oct", "10:30"


def _call_us(hospital):
    return f' To change it, call {hospital.phone}.' if hospital.phone else ''


def message_text(appointment, kind, hospital):
    day, clock = _when(appointment.starts_at, hospital)
    doctor = f'Dr {appointment.doctor.user.last_name}'
    if kind == SmsMessage.Kind.REMINDER:
        text = f'Reminder from {hospital.name}: your appointment with {doctor} is tomorrow, {day} at {clock}.'
    else:
        text = f'{hospital.name}: your appointment with {doctor} is booked for {day} at {clock}.'
    return text + _call_us(hospital)


def _enabled(hospital, kind):
    return hospital.sms_reminders if kind == SmsMessage.Kind.REMINDER else hospital.sms_booking_confirmations


def _sent_this_month():
    start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return SmsMessage.objects.filter(
        created_at__gte=start, status__in=[SmsMessage.Status.QUEUED, SmsMessage.Status.SENT]
    ).count()


def queue(appointment, kind, hospital=None):
    '''
    Record the message for this appointment slot, deciding whether it may be
    sent. Returns None when the hospital has this message switched off, or
    the existing message if one was already made for this slot.
    '''
    hospital = hospital or current_hospital()
    if not (_enabled(hospital, kind) and sms.available()):
        return None
    existing = SmsMessage.objects.filter(
        appointment=appointment, kind=kind, appointment_starts_at=appointment.starts_at
    ).first()
    if existing:
        return existing

    patient = appointment.patient
    to = sms.normalize(patient.user.phone_number)
    message = SmsMessage(
        kind=kind, patient=patient, appointment=appointment, appointment_starts_at=appointment.starts_at,
        to=to or '', body=message_text(appointment, kind, hospital),
    )  # fmt: skip
    if patient.sms_opt_out:
        message.status, message.error = SmsMessage.Status.SKIPPED, 'The patient asked not to get SMS.'
    elif not to:
        message.status, message.error = SmsMessage.Status.SKIPPED, 'No valid mobile number on file.'
    elif _sent_this_month() >= settings.SMS_MONTHLY_LIMIT_PER_HOSPITAL:
        message.status, message.error = SmsMessage.Status.SKIPPED, "This month's SMS limit has been reached."
    try:
        with transaction.atomic():
            message.save()
    except IntegrityError:  # made at the same moment by another request
        return SmsMessage.objects.get(appointment=appointment, kind=kind, appointment_starts_at=appointment.starts_at)
    return message


def deliver(message_id, hospital=None):
    '''Send a queued message through the provider and record the outcome.'''
    message = SmsMessage.objects.get(pk=message_id)
    if message.status != SmsMessage.Status.QUEUED:
        return message
    hospital = hospital or current_hospital()
    try:
        message.provider, message.provider_message_id = sms.send(
            to=message.to, body=message.body, sender=hospital.sms_sender_id
        )
    except sms.SmsError as exc:
        logger.warning('SMS %s failed: %s', message.pk, exc)
        message.status, message.error = SmsMessage.Status.FAILED, str(exc)[:255]
    else:
        message.status, message.sent_at = SmsMessage.Status.SENT, timezone.now()
    message.save()
    return message


def send_soon(message):
    '''Send without making the person who booked wait for the provider.'''
    if not settings.SMS_SEND_IN_BACKGROUND:
        deliver(message.pk)
        return
    hospital = current_hospital()
    threading.Thread(target=_deliver_in_thread, args=(hospital.pk, message.pk), name=f'sms-{message.pk}').start()


def _deliver_in_thread(hospital_id, message_id):
    try:
        hospital = Hospital.objects.get(pk=hospital_id)
        with tenant_context(hospital):
            deliver(message_id, hospital)
    except Exception:
        logger.exception('Sending SMS %s failed', message_id)
    finally:
        connections.close_all()


def send_due_reminders(hospital, now=None):
    '''
    Remind patients of tomorrow's appointments, once the hospital's day has
    reached SMS_REMINDER_HOUR. Safe to run every hour: each reminder is sent once.
    '''
    now = now or timezone.now()
    zone = ZoneInfo(hospital.timezone)
    local_now = now.astimezone(zone)
    if local_now.hour < settings.SMS_REMINDER_HOUR:
        return 0
    start = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=zone)
    appointments = Appointment.objects.filter(
        status=Appointment.Status.SCHEDULED, starts_at__gte=start, starts_at__lt=start + timedelta(days=1)
    ).select_related('patient__user', 'doctor__user')
    sent = 0
    for appointment in appointments:
        message = queue(appointment, SmsMessage.Kind.REMINDER, hospital)
        if message and message.status == SmsMessage.Status.QUEUED:
            sent += deliver(message.pk, hospital).status == SmsMessage.Status.SENT
    return sent
