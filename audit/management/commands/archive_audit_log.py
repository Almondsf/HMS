'''
Retention for the audit log, which records every view and change of patient data
and so grows fastest of all tables. Archives entries older than a date to a
compressed CSV file and, with --delete, removes them from the database.

Nothing is ever deleted automatically. Choose the retention period with your
lawyer (health records have legal retention rules), keep the archive files
safe (they contain personal data), and run this deliberately, e.g. yearly.
'''

import csv
import gzip
import os
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

from audit.models import AuditEvent
from audit.recorder import Category, record
from tenants.models import Hospital


class Command(BaseCommand):
    help = 'Archive audit log entries older than a date to .csv.gz files, and optionally delete them (--delete).'

    def add_arguments(self, parser):
        parser.add_argument('--before', required=True, help='Archive entries before this date (YYYY-MM-DD)')
        parser.add_argument('--output', required=True, help='Folder for the archive files')
        parser.add_argument('--schema', help='One hospital (or "public" for the platform); default: all')
        parser.add_argument('--delete', action='store_true', help='Remove the archived entries from the database')

    def handle(self, *args, before, output, schema, delete, **options):
        try:
            cutoff_day = datetime.strptime(before, '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError('Give --before as YYYY-MM-DD.') from exc
        youngest_allowed = timezone.localdate() - timedelta(days=settings.AUDIT_MIN_RETENTION_DAYS)
        if cutoff_day > youngest_allowed:
            raise CommandError(
                f'Entries must be kept at least {settings.AUDIT_MIN_RETENTION_DAYS} days: '
                f'use a date on or before {youngest_allowed}.'
            )
        cutoff = timezone.make_aware(datetime.combine(cutoff_day, time.min))
        os.makedirs(output, exist_ok=True)

        schemas = [schema] if schema else [get_public_schema_name(), *Hospital.objects.exclude(
            schema_name=get_public_schema_name()).values_list('schema_name', flat=True)]  # fmt: skip
        for name in schemas:
            with schema_context(name):
                archived, path = self.archive(name, cutoff, output)
                deleted = self.purge(cutoff, archived['max_id']) if delete and archived['rows'] else 0
                if archived['rows']:
                    record(
                        'audit.archived', Category.SECURITY,
                        metadata={'before': before, 'rows': archived['rows'], 'deleted': deleted,
                                  'file': os.path.basename(path)},
                    )  # fmt: skip
            self.stdout.write(
                f'  {name}: {archived["rows"]} archived to {path}' + (f', {deleted} deleted' if delete else '')
            )
        self.stdout.write(self.style.SUCCESS('Done. The archive files contain personal data: store them securely.'))

    def archive(self, name, cutoff, output):
        fields = [field.attname for field in AuditEvent._meta.concrete_fields]
        path = os.path.join(output, f'{name}-audit-before-{cutoff:%Y-%m-%d}.csv.gz')
        rows, max_id = 0, 0
        with gzip.open(path, 'wt', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(fields)
            entries = AuditEvent.objects.filter(occurred_at__lt=cutoff).order_by('pk').values_list(*fields)
            for entry in entries.iterator(chunk_size=5000):
                writer.writerow(['' if value is None else value for value in entry])
                rows += 1
                max_id = max(max_id, entry[0])
        if not rows:
            os.remove(path)
        return {'rows': rows, 'max_id': max_id}, path

    def purge(self, cutoff, max_id):
        '''Delete exactly what was archived; the trigger allows it for this transaction only.'''
        table = AuditEvent._meta.db_table
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL hms.audit_retention_purge = 'on'")
            cursor.execute(f'DELETE FROM {table} WHERE occurred_at < %s AND id <= %s', [cutoff, max_id])  # noqa: S608
            return cursor.rowcount
