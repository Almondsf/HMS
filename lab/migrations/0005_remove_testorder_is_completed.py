from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lab', '0004_copy_lab_data'),
    ]

    operations = [
        migrations.RemoveField(model_name='testorder', name='is_completed'),
    ]
