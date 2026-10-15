from django.db import migrations
from django.utils import timezone


def seed(apps, schema_editor):
    '''Starting drafts, published so signup works; marked as drafts until a lawyer approves new versions.'''
    from django.db import connection
    from django_tenants.utils import get_public_schema_name

    if connection.schema_name != get_public_schema_name():
        return
    from legal.drafts import PRIVACY, TERMS

    LegalDocument = apps.get_model('legal', 'LegalDocument')
    for kind, body in (('terms', TERMS), ('privacy', PRIVACY)):
        LegalDocument.objects.get_or_create(
            kind=kind, version='draft-1', defaults={'body': body.strip(), 'is_draft': True, 'published_at': timezone.now()}
        )


class Migration(migrations.Migration):
    dependencies = [('legal', '0001_initial')]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
