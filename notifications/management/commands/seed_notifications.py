'''
Demo notifications for a demo hospital, made by the real notification
handlers from records that exist (so wording and links are exactly what
staff would see). Spread over the last three days, the older ones read.
Only for hospitals loaded with seed_demo: never fills a real hospital's bell.
'''

import random
from collections import Counter
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, F
from django.utils import timezone
from django_tenants.utils import tenant_context

from audit.events import DomainEvent
from authentication.permissions import Role
from clinical import vitals as vitals_rules
from clinical.models import Consultation, Visit, VitalSigns
from insurance.models import Claim
from lab.models import TestOrder
from notifications import alerts
from notifications.inbox import Level, emails_paused, notify, staff
from notifications.models import Notification
from pharmacy.models import Drug
from profiles.models import RecordSequence
from scheduling.models import Appointment
from tenants.management.commands.seed_demo import SEED_MARKER
from tenants.models import Hospital


def event(name, resource, **payload):
    return DomainEvent(name=name, resource=resource, payload=payload)


class Command(BaseCommand):
    help = 'Fill the notification centre of a demo hospital (one loaded with seed_demo) with realistic notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--schema', required=True, help='The demo hospital, e.g. main')
        parser.add_argument('--reset', action='store_true', help='Delete its existing notifications first')

    def handle(self, *args, schema, reset, **options):
        hospital = Hospital.objects.filter(schema_name=schema).first()
        if hospital is None:
            raise CommandError(f'No hospital "{schema}".')
        timezone.activate(ZoneInfo(hospital.timezone))  # appointment times in the hospital's time
        with tenant_context(hospital):
            if not RecordSequence.objects.filter(name=SEED_MARKER).exists():
                raise CommandError(
                    f'"{hospital.name}" has no demo data (seed_demo): refusing to add fake notifications.'
                )
            if reset:
                Notification.objects.all().delete()
            start = timezone.now()
            with emails_paused():  # demo data: email nobody
                self.make()
            created = Notification.objects.filter(created_at__gte=start).select_related('recipient')
            self.spread_over_time(list(created))
            by_role = Counter(n.recipient.get_user_type_display() for n in created)
        summary = ', '.join(f'{count} for {role.lower()}s' for role, count in sorted(by_role.items()))
        self.stdout.write(self.style.SUCCESS(f'{sum(by_role.values())} notifications: {summary}.'))

    def make(self):
        # Doctors: patients waiting, emergencies, critical vitals
        recent = Visit.objects.select_related('patient__user', 'assigned_doctor__user').order_by('-created_at')
        for visit in recent.filter(status__in=[Visit.Status.WAITING, Visit.Status.IN_PROGRESS])[:6] or recent[:6]:
            alerts.patient_waiting(event('clinical.visit_opened', visit))
        if emergency := recent.first():
            alerts.emergency(event('clinical.emergency_arrival', emergency))
        for vitals in VitalSigns.objects.select_related(
            'visit__patient__user', 'visit__assigned_doctor__user'
        ).order_by('-recorded_at')[:40]:
            flags, critical = vitals_rules.assess(
                {field: getattr(vitals, field) for field in vitals_rules.MEASUREMENTS}
            )
            if flags:  # the demo readings are mostly normal: show the first abnormal set as critical
                alerts.critical_vitals(event('clinical.critical_vitals', vitals, flags=flags))
                break

        # Pharmacists: prescriptions; pharmacists and admins: low stock
        with_prescriptions = Consultation.objects.annotate(items=Count('prescriptions')).filter(items__gt=0)
        for consultation in with_prescriptions.select_related('visit__patient__user').order_by('-created_at')[:4]:
            alerts.prescribed(event('clinical.consultation_recorded', consultation))
        low = Drug.objects.filter(quantity_in_stock__lte=F('reorder_level')).order_by('quantity_in_stock')
        for drug in low[:2] or Drug.objects.order_by('quantity_in_stock')[:2]:
            alerts.stock_low(
                event(
                    'pharmacy.stock_low',
                    drug,
                    quantity_in_stock=drug.quantity_in_stock,
                    reorder_level=drug.reorder_level,
                )
            )

        # Cashiers: patients ready to pay
        for visit in recent.filter(status=Visit.Status.COMPLETED)[:4]:
            alerts.ready_to_pay(event('clinical.visit_completed', visit))

        # Laboratory: new requests for lab techs, results for the ordering doctor
        orders = TestOrder.objects.select_related('patient__user', 'ordered_by__user').order_by('-ordered_at')
        for order in orders.exclude(status=TestOrder.Status.COMPLETED)[:3]:
            tests = list(order.results.values_list('test__name', flat=True))
            alerts.lab_order(event('lab.order_placed', order, tests=tests))
        for order in orders.filter(status=TestOrder.Status.COMPLETED, ordered_by__isnull=False)[:3]:
            alerts.lab_results_ready(event('lab.order_completed', order))

        # Insurance: claim outcomes for cashiers and admins
        handlers = {
            Claim.Status.APPROVED: alerts.claim_approved,
            Claim.Status.REJECTED: alerts.claim_rejected,
            Claim.Status.PAID: alerts.claim_paid,
        }
        for status, handler in handlers.items():
            claim = (
                Claim.objects.filter(status=status)
                .select_related('invoice__patient__user', 'coverage__provider')
                .first()
            )
            if claim:
                handler(event(f'insurance.claim_{status}', claim))

        # Doctors: appointments booked and cancelled
        appointments = Appointment.objects.select_related('patient__user', 'doctor__user').order_by('-created_at')
        for appointment in appointments.filter(status=Appointment.Status.SCHEDULED)[:3]:
            alerts.appointment_booked(event('scheduling.appointment_booked', appointment))
        if cancelled := appointments.filter(status=Appointment.Status.CANCELLED).first():
            alerts.appointment_cancelled(event('scheduling.appointment_cancelled', cancelled))

        # Admins: the trial (as notify_subscription_status sends it)
        notify(
            staff(Role.ADMIN),
            kind='subscription.trial_ends_demo',
            level=Level.WARNING,
            title='Your free trial ends in 3 days',
            body='Choose a plan to keep everything running without interruption.',
            link='/subscription',
        )

    def spread_over_time(self, notifications):
        '''Newest first over the last three days; anything older than about a day is already read.'''
        rng = random.Random(7)  # noqa: S311  demo data, not security
        now = timezone.now()
        ages = sorted(timedelta(minutes=rng.randint(2, 3 * 24 * 60)) for _ in notifications)
        rng.shuffle(notifications)
        for notification, age in zip(notifications, ages, strict=True):
            if notification.level == Level.URGENT:
                age = timedelta(minutes=rng.randint(5, 50))  # emergencies are recent and still unread
            created = now - age
            read = created + timedelta(minutes=rng.randint(3, 90)) if age > timedelta(hours=20) else None
            Notification.objects.filter(pk=notification.pk).update(created_at=created, read_at=read)
