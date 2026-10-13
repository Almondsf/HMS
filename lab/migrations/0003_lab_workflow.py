import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    '''Reshape the lab module: catalogue rename, order status, per-test results.'''

    dependencies = [
        ('lab', '0002_rename_labtestorder_testorder_and_more'),
        ('clinical', '0002_rename_laborder_labtestorder'),
        ('profiles', '0003_alter_pharmacistprofile_user'),
    ]

    operations = [
        # Catalogue
        migrations.RenameModel(old_name='Tests', new_name='LabTest'),
        migrations.AlterModelOptions(name='labtest', options={'ordering': ['name']}),
        migrations.AddField(
            model_name='labtest', name='is_active',
            field=models.BooleanField(default=True, help_text='Retire tests instead of deleting them.'),
        ),

        # Orders
        migrations.AlterModelOptions(name='testorder', options={'ordering': ['-ordered_at']}),
        migrations.AddField(
            model_name='testorder', name='consultation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='lab_orders', to='clinical.consultation'),
        ),
        migrations.AddField(model_name='testorder', name='reason', field=models.TextField(blank=True, default=''),
                            preserve_default=False),
        migrations.AddField(
            model_name='testorder', name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'),
                                            ('completed', 'Completed'), ('cancelled', 'Cancelled')],
                                   db_index=True, default='pending', max_length=20),
        ),
        migrations.AlterField(
            model_name='testorder', name='patient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lab_orders',
                                    to='profiles.patientprofile'),
        ),
        migrations.AlterField(
            model_name='testorder', name='ordered_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='lab_orders', to='profiles.doctorprofile'),
        ),

        # Results
        migrations.RenameField(model_name='testresult', old_name='performed_by', new_name='labtech'),
        migrations.AlterField(
            model_name='testresult', name='labtech',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='test_results', to='profiles.labtechprofile'),
        ),
        migrations.RenameField(model_name='testresult', old_name='result_date', new_name='completed_at'),
        migrations.AlterField(model_name='testresult', name='completed_at',
                              field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name='testresult', name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('collected', 'Sample Collected'),
                                            ('in_progress', 'In Progress'), ('completed', 'Completed'),
                                            ('cancelled', 'Cancelled')],
                                   default='pending', max_length=20),
        ),
        migrations.AddField(model_name='testresult', name='notes', field=models.TextField(blank=True, null=True)),
        migrations.AlterField(model_name='testresult', name='result_value',
                              field=models.CharField(blank=True, max_length=100)),
        migrations.AlterField(
            model_name='testresult', name='order',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results',
                                    to='lab.testorder'),
        ),
        migrations.AlterField(
            model_name='testresult', name='test',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='results',
                                    to='lab.labtest'),
        ),
    ]
