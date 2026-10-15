'''
The platform operator's view of the business: hospitals, money coming in,
and who needs attention (trials ending, overdue payments, failed signups).
'''

from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Max, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, tenant_context

from signup.models import Signup
from subscriptions.models import PlanPrice, Subscription, SubscriptionPayment

TRIAL_ENDING_WITHIN = timedelta(days=7)
STATES = ('trialing', 'paying', 'overdue', 'lapsed', 'suspended')


def _state(subscription, now):
    '''One word for where a hospital stands: trialing, paying, overdue, lapsed or suspended.'''
    if not subscription.hospital.is_active:
        return 'suspended'
    access = subscription.access(now)
    if access == Subscription.Access.READ_ONLY:
        return 'lapsed'
    if access == Subscription.Access.WARNING:
        return 'overdue'
    return 'trialing' if subscription.status == Subscription.Status.TRIALING else 'paying'


def _row(subscription, now):
    hospital = subscription.hospital
    domain = next((d.domain for d in hospital.domains.all() if d.is_primary), '')
    return {
        'id': hospital.pk,
        'name': hospital.name,
        'domain': domain,
        'plan': hospital.plan,
        'state': _state(subscription, now),
        'current_period_end': subscription.current_period_end,
        'grace_ends_at': subscription.grace_ends_at,
        'days_left': subscription.days_left(now),
        'billing_email': subscription.billing_email,
    }


def _monthly_value(subscription, prices):
    '''What a paying hospital brings in per month, at today's prices (yearly / 12).'''
    amount = prices.get((subscription.hospital.plan, subscription.interval))
    if amount is None:
        return Decimal(0)
    return amount / 12 if subscription.interval == 'yearly' else amount


def overview(now=None):
    now = now or timezone.now()
    subscriptions = list(
        Subscription.objects.exclude(hospital__schema_name=get_public_schema_name())
        .select_related('hospital')
        .prefetch_related('hospital__domains')
    )
    prices = {(price.plan, price.interval): price.amount for price in PlanPrice.objects.filter(is_active=True)}

    states = Counter()
    plans = Counter()
    monthly_revenue = Decimal(0)
    trials_ending, overdue, lapsed = [], [], []
    for subscription in subscriptions:
        state = _state(subscription, now)
        states[state] += 1
        if state != 'suspended':
            plans[subscription.hospital.plan] += 1
        if state in ('paying', 'overdue') and not subscription.cancel_at_period_end:
            monthly_revenue += _monthly_value(subscription, prices)
        if state == 'trialing' and subscription.current_period_end <= now + TRIAL_ENDING_WITHIN:
            trials_ending.append(_row(subscription, now))
        elif state == 'overdue':
            overdue.append(_row(subscription, now))
        elif state == 'lapsed':
            lapsed.append(_row(subscription, now))

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    six_months_ago = (month_start - timedelta(days=150)).replace(day=1)
    payments = SubscriptionPayment.objects.filter(paid_at__gte=six_months_ago)
    by_month = {
        row['month'].strftime('%Y-%m'): row['total']
        for row in payments.annotate(month=TruncMonth('paid_at')).values('month').annotate(total=Sum('amount'))
    }
    months = []
    cursor = six_months_ago
    while cursor <= month_start:
        key = cursor.strftime('%Y-%m')
        months.append({'month': key, 'total': by_month.get(key, Decimal(0))})
        cursor = (cursor + timedelta(days=32)).replace(day=1)

    this_month = payments.filter(paid_at__gte=month_start)
    recent_signups = Signup.objects.filter(created_at__gte=now - timedelta(days=30))

    return {
        'hospitals': {'total': len(subscriptions), **{state: states[state] for state in STATES}},
        'plans': dict(plans),
        'revenue': {
            'monthly_recurring': monthly_revenue.quantize(Decimal('0.01')),
            'this_month': this_month.aggregate(total=Sum('amount'))['total'] or Decimal(0),
            'this_month_by_plan': {
                row['plan']: row['total'] for row in this_month.values('plan').annotate(total=Sum('amount'))
            },
            'by_month': months,
        },
        'signups': {
            'last_30_days': dict(recent_signups.values_list('status').annotate(count=Count('id'))),
            'stalled': Signup.objects.filter(status=Signup.Status.PROVISIONING)
            .filter(provisioning_started_at__lt=now - timedelta(minutes=15))
            .count(),
        },
        'attention': {
            'trials_ending': sorted(trials_ending, key=lambda row: row['current_period_end']),
            'overdue': sorted(overdue, key=lambda row: row['grace_ends_at']),
            'lapsed': sorted(lapsed, key=lambda row: row['current_period_end'], reverse=True)[:20],
        },
    }


def usage(hospital):
    '''How much a hospital actually uses the system (looks inside its schema).'''
    from audit.models import AuditEvent
    from authentication.models import User
    from clinical.models import Visit
    from profiles.models import PatientProfile

    since = timezone.now() - timedelta(days=30)
    with tenant_context(hospital):
        staff = User.objects.filter(is_active=True).exclude(user_type=User.UserType.PATIENT)
        return {
            'active_staff': staff.count(),
            'patients': PatientProfile.objects.count(),
            'visits_last_30_days': Visit.objects.filter(created_at__gte=since).count(),
            'last_sign_in': staff.aggregate(last=Max('last_login'))['last'],
            'last_activity': AuditEvent.objects.aggregate(last=Max('occurred_at'))['last'],
        }
