from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_public_schema_name

from tenants.models import Hospital
from tenants.services import copy_hospital_data


class Command(BaseCommand):
    help = (
        'One-time upgrade: copy the data of a pre-multi-tenancy database (stored in the public schema) '
        'into a hospital created with create_hospital. The source data is left untouched.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--schema', required=True, help='Target hospital schema')
        parser.add_argument('--source', default=get_public_schema_name(), help='Schema to copy from')
        parser.add_argument('--force', action='store_true', help="Overwrite the target even if it has users")

    def handle(self, *args, schema, source, force, **options):
        if not Hospital.objects.filter(schema_name=schema).exists():
            raise CommandError(f'No hospital with schema "{schema}". Create it with create_hospital first.')
        try:
            copied = copy_hospital_data(source_schema=source, target_schema=schema, force=force)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc

        for table, rows in copied.items():
            if rows:
                self.stdout.write(f'  {table}: {rows}')
        self.stdout.write(self.style.SUCCESS(f'Copied {sum(copied.values())} rows from "{source}" into "{schema}".'))
