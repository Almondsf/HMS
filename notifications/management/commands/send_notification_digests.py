from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, tenant_context

from notifications import emails
from tenants.models import Hospital


class Command(BaseCommand):
    help = (
        'Email each staff member a morning summary of unread notifications (if they chose it). '
        "Runs hourly; each hospital's go out once its morning reaches NOTIFICATION_DIGEST_HOUR."
    )

    def handle(self, *args, **options):
        total = 0
        for hospital in Hospital.objects.exclude(schema_name=get_public_schema_name()).filter(is_active=True):
            with tenant_context(hospital):
                total += emails.send_digests(hospital)
        self.stdout.write(self.style.SUCCESS(f'{total} daily summary email(s) sent.'))
