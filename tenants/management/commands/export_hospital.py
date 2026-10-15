from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from audit.recorder import Category, record
from tenants import export
from tenants.models import Hospital


class Command(BaseCommand):
    help = (
        "Export all of a hospital's records to a ZIP of CSV files, e.g. for a hospital that has left. "
        'The file contains patient data: hand it over securely and delete your copy.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--schema', required=True, help='The hospital identifier, e.g. stlukes')
        parser.add_argument('--output', help='File to write (default: <schema>-records-<date>.zip)')

    def handle(self, *args, schema, output, **options):
        hospital = Hospital.objects.filter(schema_name=schema).first()
        if hospital is None:
            raise CommandError(f'No hospital "{schema}".')
        path = output or export.filename(hospital)
        with tenant_context(hospital), open(path, 'wb') as file:
            counts = export.write_export(file, hospital)
            record(
                'data.exported', Category.SECURITY, metadata={'rows': sum(counts.values()), 'by': 'platform command'}
            )
        self.stdout.write(self.style.SUCCESS(f'Wrote {path}: {sum(counts.values())} rows in {len(counts)} files.'))
