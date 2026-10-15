from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, tenant_context

from helpers import sms
from notifications import services
from subscriptions.models import Subscription
from tenants.models import Hospital


class Command(BaseCommand):
    help = (
        "SMS patients about tomorrow's appointments, in hospitals that switched reminders on. "
        'Run every hour (e.g. a Render cron job): reminders go out once the hospital\'s day reaches '
        'SMS_REMINDER_HOUR, and each is sent only once.'
    )

    def handle(self, *args, **options):
        if not sms.available():
            self.stdout.write('SMS is not set up (SMS_BACKEND); nothing to do.')
            return
        hospitals = Hospital.objects.exclude(schema_name=get_public_schema_name()).filter(
            is_active=True, sms_reminders=True
        )
        total = 0
        for hospital in hospitals:
            subscription = Subscription.objects.filter(hospital=hospital).first()
            if subscription and subscription.access() == Subscription.Access.READ_ONLY:
                continue  # lapsed: no new costs until they pay
            with tenant_context(hospital):
                sent = services.send_due_reminders(hospital)
            if sent:
                self.stdout.write(f'  {hospital.name}: {sent} reminder(s) sent')
            total += sent
        self.stdout.write(self.style.SUCCESS(f'Done: {total} reminder(s) sent.'))
