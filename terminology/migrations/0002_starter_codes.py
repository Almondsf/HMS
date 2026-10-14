from django.db import migrations

from terminology.starter_codes import STARTER_CODES


def load(apps, schema_editor):
    Icd10Code = apps.get_model('terminology', 'Icd10Code')
    for code, title in STARTER_CODES:
        Icd10Code.objects.get_or_create(code=code, defaults={'title': title})


class Migration(migrations.Migration):
    dependencies = [('terminology', '0001_initial')]

    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
