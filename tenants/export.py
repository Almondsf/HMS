'''
Export everything a hospital has recorded, as a ZIP of CSV files (one per
kind of record) that opens in Excel or imports anywhere. Hospitals own
their data: they can take it at any time, including after they stop paying.

Columns are the database field names; "<name>_id" columns hold the id of a
row in another file, so the files can be joined back together. Passwords
and session tokens are never exported.
'''

import csv
import io
import json
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.utils import timezone

# Apps whose tables live in each hospital's schema and hold its records
EXPORT_APPS = [
    'authentication', 'profiles', 'scheduling', 'clinical', 'lab', 'pharmacy', 'billing', 'insurance',
    'notifications', 'audit',
]  # fmt: skip
HIDDEN_FIELDS = {'authentication.user': {'password'}}

# A spreadsheet runs cells starting with these as formulas; a text like "=HYPERLINK(...)"
# in a patient's notes must not become a live formula on the admin's computer.
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')
HARMLESS = re.compile(r'^[+-][\d\s().-]*$')  # phone numbers and signed numbers


def export_models():
    models = []
    for label in EXPORT_APPS:
        for model in apps.get_app_config(label).get_models():
            if model._meta.managed and not model._meta.proxy:
                models.append(model)
    return models


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (date, Decimal)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    if isinstance(value, str) and value.startswith(FORMULA_START) and not HARMLESS.match(value):
        return "'" + value
    return value


README = '''{name}: all records, exported {exported_at} (UTC)

One CSV file per kind of record (UTF-8, opens in Excel). The first row of each
file names the columns. Columns ending in "_id" hold the id of a row in another
file: for example clinical_visit.csv "patient_id" is the "id" in
profiles_patientprofile.csv, and profiles_patientprofile.csv "user_id" is the
"id" in authentication_user.csv (names, phone numbers).

Times are in UTC (ISO 8601). Text that a spreadsheet would treat as a formula
starts with an apostrophe ('). Passwords are not included.

manifest.json lists every file and its number of rows.

This file contains confidential patient information. Store it securely and
delete it when you no longer need it.
'''


def write_export(fileobj, hospital):
    '''Write the ZIP to fileobj (inside the hospital's schema); returns {file: rows}.'''
    exported_at = timezone.now()
    counts = {}
    with zipfile.ZipFile(fileobj, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for model in export_models():
            hidden = HIDDEN_FIELDS.get(model._meta.label_lower, set())
            columns = [field.attname for field in model._meta.concrete_fields if field.name not in hidden]
            name = f'{model._meta.app_label}_{model._meta.model_name}.csv'
            rows = 0
            with archive.open(name, 'w') as raw:
                text = io.TextIOWrapper(raw, encoding='utf-8-sig', newline='')  # BOM: Excel reads UTF-8 correctly
                writer = csv.writer(text)
                writer.writerow(columns)
                for row in model.objects.order_by('pk').values_list(*columns).iterator(chunk_size=2000):
                    writer.writerow([_cell(value) for value in row])
                    rows += 1
                text.flush()
                text.detach()
            counts[name] = rows
        archive.writestr('README.txt', README.format(name=hospital.name, exported_at=f'{exported_at:%Y-%m-%d %H:%M}'))
        archive.writestr(
            'manifest.json',
            json.dumps(
                {
                    'hospital': hospital.name,
                    'schema': hospital.schema_name,
                    'exported_at': exported_at.isoformat(),
                    'files': counts,
                },
                indent=2,
            ),
        )
    return counts


def filename(hospital):
    return f'{hospital.schema_name}-records-{timezone.now():%Y-%m-%d}.zip'
