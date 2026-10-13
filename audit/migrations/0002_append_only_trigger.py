from django.db import migrations

# Defence in depth: even raw SQL from the application's database account can't
# rewrite or erase audit history. (A DB superuser can still drop the trigger,
# e.g. for a documented retention purge.)
CREATE = '''
CREATE OR REPLACE FUNCTION audit_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditevent is append-only (%% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_event_append_only
    BEFORE UPDATE OR DELETE ON audit_auditevent
    FOR EACH ROW EXECUTE FUNCTION audit_event_append_only();
'''

DROP = '''
DROP TRIGGER IF EXISTS audit_event_append_only ON audit_auditevent;
DROP FUNCTION IF EXISTS audit_event_append_only();
'''


def create_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(CREATE)


def drop_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(DROP)


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_trigger, drop_trigger),
    ]
