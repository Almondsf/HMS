'''
Who hears about what. Each handler turns a domain event into notifications
for the staff who need to act, linking to the screen they'd open next.
Handlers run after the action has been saved; a failure here never undoes it.
'''

from django.utils import timezone

from audit import events
from authentication.permissions import Role

from .inbox import Level, notify, staff


def _name(patient):
    return patient.user.get_full_name()


def _doctor(doctor_profile):
    return doctor_profile.user if doctor_profile is not None else None


# ---- Clinical ----


@events.subscribe('clinical.visit_opened')
def patient_waiting(event):
    visit = event.resource
    notify(
        [_doctor(visit.assigned_doctor)],
        kind=event.name,
        title=f'{_name(visit.patient)} is waiting to see you',
        body=visit.reason_for_visit,
        link=f'/visits/{visit.pk}',
    )


@events.subscribe('clinical.emergency_arrival')
def emergency(event):
    visit = event.resource
    notify(
        [_doctor(visit.assigned_doctor), *staff(Role.NURSE)],
        kind=event.name,
        level=Level.URGENT,
        title=f'Emergency: {_name(visit.patient)}',
        body=f'Triaged as an emergency, in Dr {visit.assigned_doctor.user.last_name}\'s queue.',
        link=f'/visits/{visit.pk}',
    )


@events.subscribe('clinical.critical_vitals')
def critical_vitals(event):
    vitals = event.resource
    visit = vitals.visit
    notify(
        [_doctor(visit.assigned_doctor), *staff(Role.NURSE)],
        kind=event.name,
        level=Level.URGENT,
        title=f'Critical vital signs: {_name(visit.patient)}',
        body=', '.join(event.payload.get('flags') or []).capitalize(),
        link=f'/visits/{visit.pk}',
    )


@events.subscribe('clinical.consultation_recorded')
def prescribed(event):
    consultation = event.resource
    count = consultation.prescriptions.count()
    if not count:
        return
    visit = consultation.visit
    notify(
        staff(Role.PHARMACIST),
        kind='clinical.prescribed',
        title=f'New prescription for {_name(visit.patient)}',
        body=f'{count} item{"s" if count != 1 else ""} from Dr {visit.assigned_doctor.user.last_name}',
        link='/pharmacy',
    )


@events.subscribe('clinical.visit_completed')
def ready_to_pay(event):
    visit = event.resource
    invoice = visit.invoices.exclude(status='void').order_by('-created_at').first()
    if invoice is None or invoice.status == 'paid' or invoice.total <= 0:
        return
    notify(
        staff(Role.CASHIER),
        kind=event.name,
        title=f'{_name(visit.patient)} is ready to pay',
        body=f'Seen by Dr {visit.assigned_doctor.user.last_name}. Invoice {invoice.number}.',
        link=f'/billing/invoices/{invoice.pk}',
    )


# ---- Laboratory ----


@events.subscribe('lab.order_placed')
def lab_order(event):
    order = event.resource
    tests = event.payload.get('tests') or []
    notify(
        staff(Role.LAB_TECHNICIAN),
        kind=event.name,
        title=f'Lab request for {_name(order.patient)}',
        body=', '.join(tests),
        link='/lab',
    )


@events.subscribe('lab.order_completed')
def lab_results_ready(event):
    order = event.resource
    link = f'/visits/{order.consultation.visit_id}' if order.consultation_id else f'/lab/orders/{order.pk}/print'
    notify(
        [_doctor(order.ordered_by)],
        kind=event.name,
        title=f'Lab results ready: {_name(order.patient)}',
        body='All requested tests are complete.',
        link=link,
    )


# ---- Pharmacy ----


@events.subscribe('pharmacy.stock_low')
def stock_low(event):
    drug = event.resource
    notify(
        staff(Role.PHARMACIST, Role.ADMIN),
        kind=event.name,
        level=Level.WARNING,
        title=f'{drug.name} is running low',
        body=f'{event.payload.get("quantity_in_stock")} left (reorder at {event.payload.get("reorder_level")}).',
        link='/pharmacy/drugs',
    )


# ---- Insurance ----


def _claim_update(event, title, level=Level.INFO):
    claim = event.resource
    notify(
        staff(Role.CASHIER, Role.ADMIN),
        kind=event.name,
        level=level,
        title=title.format(patient=_name(claim.invoice.patient), provider=claim.coverage.provider.name),
        link='/insurance/claims',
    )


@events.subscribe('insurance.claim_approved')
def claim_approved(event):
    _claim_update(event, '{provider} approved the claim for {patient}')


@events.subscribe('insurance.claim_rejected')
def claim_rejected(event):
    _claim_update(event, '{provider} rejected the claim for {patient}', Level.WARNING)


@events.subscribe('insurance.claim_paid')
def claim_paid(event):
    _claim_update(event, '{provider} paid the claim for {patient}')


# ---- Appointments ----


def _appointment(event, title):
    appointment = event.resource
    when = timezone.localtime(appointment.starts_at)  # the hospital's time zone
    notify(
        [_doctor(appointment.doctor)],
        kind=event.name,
        title=title.format(patient=_name(appointment.patient)),
        body=f'{when:%a} {when.day} {when:%b}, {when:%H:%M}',
        link='/appointments',
    )


@events.subscribe('scheduling.appointment_booked')
def appointment_booked(event):
    _appointment(event, 'New appointment: {patient}')


@events.subscribe('scheduling.appointment_cancelled')
def appointment_cancelled(event):
    _appointment(event, 'Appointment cancelled: {patient}')
