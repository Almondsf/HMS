from django.db import migrations


def forwards(apps, schema_editor):
    TestOrder = apps.get_model('lab', 'TestOrder')
    TestResult = apps.get_model('lab', 'TestResult')
    LabTest = apps.get_model('lab', 'LabTest')
    LegacyLabOrder = apps.get_model('clinical', 'LabTestOrder')

    # Old boolean flag -> status
    TestOrder.objects.filter(is_completed=True).update(status='completed')
    # Results created before statuses existed were final results
    TestResult.objects.exclude(result_value='').update(status='completed')

    # Lab orders raised from consultations used to live in clinical.LabTestOrder
    # as free text. Move them into the lab module, creating catalogue entries
    # (cost 0, for the lab to price) for any test names not yet in it.
    for legacy in LegacyLabOrder.objects.select_related('consultation__visit'):
        visit = legacy.consultation.visit
        test, _ = LabTest.objects.get_or_create(name=legacy.test_name, defaults={'cost': 0})
        order = TestOrder.objects.create(
            patient_id=visit.patient_id,
            consultation_id=legacy.consultation_id,
            ordered_by_id=visit.assigned_doctor_id,
            reason=legacy.reason or '',
            status=legacy.status,
            is_completed=legacy.status == 'completed',
        )
        TestResult.objects.create(order=order, test=test, status=legacy.status)


class Migration(migrations.Migration):

    dependencies = [
        ('lab', '0003_lab_workflow'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
