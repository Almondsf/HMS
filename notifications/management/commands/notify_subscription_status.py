from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, tenant_context

from authentication.permissions import Role
from notifications.inbox import Level, notify, staff
from subscriptions.models import Subscription

TRIAL_MILESTONES = (7, 3, 1)


def subscription_notices(subscription, today):
    '''(kind, level, title, body) to send to the hospital's admins now, or None.'''
    access = subscription.access()
    end = subscription.current_period_end
    if subscription.status == Subscription.Status.TRIALING and access == Subscription.Access.FULL:
        days = subscription.days_left()
        if days in TRIAL_MILESTONES:
            return (
                f'subscription.trial_ends_{end:%Y%m%d}_{days}',
                Level.WARNING if days <= 3 else Level.INFO,
                f'Your free trial ends in {days} day{"s" if days != 1 else ""}',
                'Choose a plan to keep everything running without interruption.',
            )
    if access == Subscription.Access.WARNING:
        return (
            f'subscription.overdue_{today:%Y%m%d}',
            Level.WARNING,
            'Subscription payment is overdue',
            f'Records become read-only after {timezone.localtime(subscription.grace_ends_at):%d %b}. Pay to avoid it.',
        )
    if access == Subscription.Access.READ_ONLY:
        return (
            f'subscription.lapsed_{today:%Y%m%d}',
            Level.URGENT,
            'Records are read-only: the subscription has lapsed',
            'Staff can view records but not save anything new until the subscription is paid.',
        )
    return None


class Command(BaseCommand):
    help = "Tell hospital admins (in their notification centre) when the trial is ending or payment is overdue."

    def handle(self, *args, **options):
        sent = 0
        today = timezone.localdate()
        subscriptions = Subscription.objects.select_related('hospital').filter(hospital__is_active=True)
        for subscription in subscriptions.exclude(hospital__schema_name=get_public_schema_name()):
            notice = subscription_notices(subscription, today)
            if notice is None:
                continue
            kind, level, title, body = notice
            with tenant_context(subscription.hospital):
                sent += len(
                    notify(
                        staff(Role.ADMIN),
                        kind=kind,
                        level=level,
                        title=title,
                        body=body,
                        link='/subscription',
                        once=True,
                    )
                )
        self.stdout.write(self.style.SUCCESS(f'{sent} subscription notice(s) sent.'))
