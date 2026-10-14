'''
A fingerprint of the database: per schema (platform and every hospital),
row counts of the important tables, applied migrations, and whether the
audit log's append-only trigger is in place. Run it on the source and on a
restored backup: identical output means the restore is complete.

    python manage.py database_report > before.json
'''

import json

from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context

# Tables that matter most if lost
TABLES = {
    'users': 'users',
    'patients': 'profiles_patientprofile',
    'visits': 'clinical_visit',
    'consultations': 'clinical_consultation',
    'diagnoses': 'clinical_diagnosis',
    'prescriptions': 'clinical_prescription',
    'lab_results': 'lab_testresult',
    'dispensed_items': 'pharmacy_dispenseditem',
    'invoices': 'billing_invoice',
    'payments': 'billing_payment',
    'claims': 'insurance_claim',
    'appointments': 'scheduling_appointment',
    'audit_events': 'audit_auditevent',
    'hospitals': 'tenants_hospital',
}


def _schema_report(cursor, schema):
    cursor.execute('SELECT table_name FROM information_schema.tables WHERE table_schema = %s', [schema])
    present = {row[0] for row in cursor.fetchall()}
    counts = {}
    for label, table in TABLES.items():
        if table in present:
            cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')  # noqa: S608 (fixed names)
            counts[label] = cursor.fetchone()[0]
    cursor.execute(f'SELECT COUNT(*) FROM "{schema}".django_migrations')  # noqa: S608
    migrations = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = %s "
        "AND trigger_name = 'audit_event_append_only'",
        [schema],
    )
    audit_protected = cursor.fetchone()[0] > 0
    return {'rows': counts, 'migrations_applied': migrations, 'audit_log_append_only': audit_protected}


class Command(BaseCommand):
    help = 'Print a JSON fingerprint of the database (row counts, migrations, audit protection) per schema.'

    def handle(self, *args, **options):
        public = get_public_schema_name()
        with schema_context(public):
            hospitals = sorted(
                get_tenant_model().objects.exclude(schema_name=public).values_list('schema_name', flat=True)
            )
        report = {}
        with connection.cursor() as cursor:
            for schema in [public, *hospitals]:
                report[schema] = _schema_report(cursor, schema)
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
