from django.db import migrations


def assign_mrns(apps, schema_editor):
    '''Give existing patients record numbers in registration order.'''
    PatientProfile = apps.get_model('profiles', 'PatientProfile')
    RecordSequence = apps.get_model('profiles', 'RecordSequence')
    Hospital = apps.get_model('tenants', 'Hospital')

    # Hospitals live in the shared schema, visible from each hospital's schema
    hospital = Hospital.objects.filter(schema_name=schema_editor.connection.schema_name).first()
    prefix = hospital.mrn_prefix if hospital else 'MRN'

    number = 0
    for number, patient in enumerate(PatientProfile.objects.filter(mrn__isnull=True).order_by('id'), start=1):
        patient.mrn = f'{prefix}-{number:06d}'
        patient.save(update_fields=['mrn'])
    RecordSequence.objects.update_or_create(name='mrn', defaults={'last_value': number})


class Migration(migrations.Migration):
    dependencies = [
        ('profiles', '0004_directory'),
        ('tenants', '0002_hospital_settings'),
    ]

    operations = [
        migrations.RunPython(assign_mrns, migrations.RunPython.noop),
    ]
