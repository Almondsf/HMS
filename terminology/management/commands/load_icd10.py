import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from terminology.models import Icd10Code


class Command(BaseCommand):
    help = (
        'Load ICD-10 codes from a CSV file with columns: code, title (header row optional). '
        'Existing codes are updated; codes are never deleted.'
    )

    def add_arguments(self, parser):
        parser.add_argument('csv_file')
        parser.add_argument('--deactivate-missing', action='store_true', help='Retire codes that are not in the file')

    @transaction.atomic
    def handle(self, *args, csv_file, deactivate_missing, **options):
        try:
            with open(csv_file, newline='', encoding='utf-8-sig') as handle:
                rows = [row for row in csv.reader(handle) if row]
        except OSError as exc:
            raise CommandError(f'Cannot read {csv_file}: {exc}') from exc

        if rows and rows[0][0].strip().lower() == 'code':
            rows = rows[1:]
        seen, created = set(), 0
        for line, row in enumerate(rows, start=1):
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                raise CommandError(f'Row {line}: expected "code,title", got {row!r}')
            code, title = row[0].strip().upper(), row[1].strip()[:255]
            _, was_created = Icd10Code.objects.update_or_create(code=code, defaults={'title': title, 'is_active': True})
            created += was_created
            seen.add(code)

        retired = 0
        if deactivate_missing:
            retired = Icd10Code.objects.exclude(code__in=seen).filter(is_active=True).update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(
                f'{len(seen)} codes loaded ({created} new, {len(seen) - created} updated, {retired} retired).'
            )
        )
