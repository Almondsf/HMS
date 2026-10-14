from django.conf import settings
from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name

from tenants.models import Domain, Hospital


class Command(BaseCommand):
    help = 'Register the platform (public schema) and its domains. Safe to run on every deploy.'

    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='*', help='Extra platform hostnames (PLATFORM_DOMAINS are always added)')

    def handle(self, *args, domains, **options):
        platform, created = Hospital.objects.get_or_create(
            schema_name=get_public_schema_name(), defaults={'name': 'Platform'}
        )
        self.stdout.write(f"{'Created' if created else 'Found'} platform tenant.")

        for index, hostname in enumerate(dict.fromkeys([*settings.PLATFORM_DOMAINS, *domains])):
            _, added = Domain.objects.get_or_create(
                domain=hostname, defaults={'tenant': platform, 'is_primary': index == 0}
            )
            if added:
                self.stdout.write(f'Added platform domain {hostname}')
