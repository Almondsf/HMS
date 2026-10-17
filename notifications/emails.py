'''
Notifications by email: important ones right away, the rest in a morning
summary. Each person chooses (User.email_notifications): everything, important
only, or nothing.

Email is less protected than the app (which needs a password, and two-factor
for admins), so emails never carry patient details: clinical notifications
are described by type only ("Lab results ready"), with a link to open them
in the app. Notices without patient data (subscription, stock) are sent in full.
'''

import logging
import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection, connections
from django.utils import timezone
from django_tenants.utils import tenant_context

from authentication.models import User
from tenants.models import Hospital

from .models import Notification

logger = logging.getLogger('hms.notifications')

Choice = User.EmailNotifications

# What an email may say about each kind of notification: never who the patient is
SAFE_DESCRIPTIONS = {
    'clinical.visit_opened': 'A patient is waiting to see you',
    'clinical.emergency_arrival': 'An emergency patient has arrived',
    'clinical.critical_vitals': 'Critical vital signs were recorded',
    'clinical.prescribed': 'A new prescription is waiting',
    'clinical.visit_completed': 'A patient is ready to pay',
    'lab.order_placed': 'A new lab request is waiting',
    'lab.order_completed': 'Lab results are ready',
    'insurance.claim_approved': 'An insurance claim was approved',
    'insurance.claim_rejected': 'An insurance claim was rejected',
    'insurance.claim_paid': 'An insurance claim was paid',
    'scheduling.appointment_booked': 'A new appointment was booked',
    'scheduling.appointment_cancelled': 'An appointment was cancelled',
}
# No patient data in these: safe to send as written
FULL_TEXT_PREFIXES = ('subscription.', 'pharmacy.stock_low')


def is_important(notification):
    return notification.level == Notification.Level.URGENT or notification.kind.startswith('subscription.')


def describe(notification):
    '''(headline, detail) that's safe to put in an email.'''
    if notification.kind.startswith(FULL_TEXT_PREFIXES):
        return notification.title, notification.body
    return SAFE_DESCRIPTIONS.get(notification.kind, 'You have a new notification'), ''


def app_link(hospital, path='/'):
    '''An absolute link into this hospital's web app (no request needed).'''
    domain = hospital.domains.filter(is_primary=True).values_list('domain', flat=True).first() or ''
    if settings.FRONTEND_URL:
        base = settings.FRONTEND_URL.format(subdomain=domain.split('.')[0], host=domain)
    else:
        base = f'https://{domain}'
    return f'{base.rstrip("/")}/{path.lstrip("/")}'


def _footer(hospital):
    return (
        f'\n\n{hospital.name} on {settings.PRODUCT_NAME}\n'
        f'Choose which emails you get: {app_link(hospital, "/notifications")}'
    )


# ---- Important notices, right away ----


def send_important(notifications):
    '''Called as notifications are created: email the important ones (in the background).'''
    ids = [n.pk for n in notifications if is_important(n)]
    if not ids:
        return
    hospital_id = connection.tenant.pk
    if settings.NOTIFICATION_EMAILS_IN_BACKGROUND:
        threading.Thread(target=_send_in_thread, args=(hospital_id, ids), name='notification-emails').start()
    else:
        _send_important(Hospital.objects.get(pk=hospital_id), ids)


def _send_in_thread(hospital_id, ids):
    try:
        hospital = Hospital.objects.get(pk=hospital_id)
        with tenant_context(hospital):
            _send_important(hospital, ids)
    except Exception:
        logger.exception('Sending notification emails failed')
    finally:
        connections.close_all()


def _send_important(hospital, ids):
    notifications = Notification.objects.filter(
        pk__in=ids,
        emailed_at__isnull=True,
        recipient__is_active=True,
        recipient__email_notifications__in=[Choice.ALL, Choice.IMPORTANT],
    ).select_related('recipient')
    for notification in notifications:
        if not notification.recipient.email:
            continue
        headline, detail = describe(notification)
        urgent = notification.level == Notification.Level.URGENT
        try:
            send_mail(
                subject=f'{"Urgent: " if urgent else ""}{headline}',
                message='\n'.join(
                    [f'{headline}.', *([detail] if detail else []), '']
                    + [f'Open it: {app_link(hospital, notification.link or "/notifications")}']
                )
                + _footer(hospital),
                from_email=None,
                recipient_list=[notification.recipient.email],
            )
        except Exception:
            logger.exception('Could not email notification %s', notification.pk)
            continue
        Notification.objects.filter(pk=notification.pk).update(emailed_at=timezone.now())


# ---- The morning summary ----


def send_digests(hospital, now=None):
    '''
    Once a day, after NOTIFICATION_DIGEST_HOUR in the hospital's time: one email per
    person listing what's still unread and not emailed yet. Returns emails sent.
    '''
    now = now or timezone.now()
    local = now.astimezone(ZoneInfo(hospital.timezone))
    if local.hour < settings.NOTIFICATION_DIGEST_HOUR:
        return 0
    today = local.date()
    since = datetime.combine(today - timedelta(days=7), time.min, tzinfo=local.tzinfo)
    people = User.objects.filter(is_active=True, email_notifications=Choice.ALL).exclude(email='')
    people = people.exclude(notification_digest_sent_on=today).exclude(user_type=User.UserType.PATIENT)
    sent = 0
    for person in people:
        waiting = list(
            Notification.objects.filter(
                recipient=person, read_at__isnull=True, emailed_at__isnull=True, created_at__gte=since
            ).order_by('-created_at')[:50]
        )
        if waiting:
            lines = []
            for notification in waiting[:20]:
                headline, _ = describe(notification)
                lines.append(f'- {headline}')
            more = f'\n…and {len(waiting) - 20} more.' if len(waiting) > 20 else ''
            try:
                send_mail(
                    subject=f'{hospital.name}: {len(waiting)} notification{"s" if len(waiting) != 1 else ""} waiting',
                    message=(
                        f'Good morning {person.first_name},\n\nWaiting for you in {settings.PRODUCT_NAME}:\n\n'
                        + '\n'.join(lines)
                        + more
                        + f'\n\nSee them all: {app_link(hospital, "/notifications")}'
                        + _footer(hospital)
                    ),
                    from_email=None,
                    recipient_list=[person.email],
                )
            except Exception:
                logger.exception('Could not send the daily summary to user %s', person.pk)
                continue
            Notification.objects.filter(pk__in=[n.pk for n in waiting]).update(emailed_at=now)
            sent += 1
        User.objects.filter(pk=person.pk).update(notification_digest_sent_on=today)
    return sent
