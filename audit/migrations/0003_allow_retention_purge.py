from django.db import migrations

# The audit log stays append-only. The single exception: the archive_audit_log
# command may delete rows it has just archived, by setting hms.audit_retention_purge
# for its own transaction only. Updates are never allowed.
ALLOW_PURGE = '''
CREATE OR REPLACE FUNCTION audit_event_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('hms.audit_retention_purge', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit_auditevent is append-only (%% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;
'''

STRICT = '''
CREATE OR REPLACE FUNCTION audit_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditevent is append-only (%% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;
'''


def allow_purge(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(ALLOW_PURGE)


def strict(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(STRICT)


class Migration(migrations.Migration):
    dependencies = [('audit', '0002_append_only_trigger')]

    operations = [migrations.RunPython(allow_purge, strict)]
