'''Hospital (tenant) lifecycle: provisioning and data moves.'''

import re

from django.apps import apps
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name, schema_context, schema_exists, tenant_context
from psycopg2 import sql

from audit import events
from authentication.models import User
from subscriptions import services as subscriptions

from .models import Domain, Hospital

SCHEMA_NAME = re.compile(r'^[a-z][a-z0-9_]{1,39}$')
RESERVED_SCHEMAS = {'public', 'information_schema', 'template', 'test'}


def default_domain(schema_name):
    return f"{schema_name.replace('_', '-')}.{settings.TENANT_BASE_DOMAIN}"


def validate_new_hospital(*, schema_name, domain):
    errors = {}
    if not SCHEMA_NAME.match(schema_name) or schema_name in RESERVED_SCHEMAS or schema_name.startswith('pg_'):
        errors['schema_name'] = 'Use 2-40 lowercase letters, digits or underscores, starting with a letter.'
    elif Hospital.objects.filter(schema_name=schema_name).exists() or schema_exists(schema_name):
        errors['schema_name'] = 'A hospital with this identifier already exists.'
    if Domain.objects.filter(domain=domain).exists():
        errors['domain'] = 'This address is already in use.'
    if errors:
        raise ValidationError(errors)


def provision_hospital(
    *,
    name,
    schema_name,
    admin_email,
    admin_first_name,
    admin_last_name,
    domain=None,
    plan=Hospital.Plan.BASIC,
    contact_email='',
    admin_password=None,
    admin_password_hash=None,
):
    '''
    Create a hospital: its schema (with all tables), its address and its first
    admin user. Either everything is created or nothing is left behind.
    Give the admin's password, or its hash (self-serve signup never keeps
    the password itself).
    '''
    if (admin_password is None) == (admin_password_hash is None):
        raise ValueError('Give exactly one of admin_password and admin_password_hash.')
    domain = domain or default_domain(schema_name)
    with schema_context(get_public_schema_name()):
        validate_new_hospital(schema_name=schema_name, domain=domain)
        if admin_password is not None:
            validate_password(admin_password)

        hospital = Hospital(name=name, schema_name=schema_name, plan=plan, contact_email=contact_email or admin_email)
        hospital.save(verbosity=0)  # creates the schema and runs all hospital migrations in it
        try:
            Domain.objects.create(domain=domain, tenant=hospital, is_primary=True)
            with tenant_context(hospital):
                admin = User.objects.create_user(
                    email=admin_email,
                    password=admin_password,
                    first_name=admin_first_name,
                    last_name=admin_last_name,
                    user_type=User.UserType.ADMIN,
                    is_staff=True,
                    is_admin=True,
                )
                if admin_password_hash is not None:
                    admin.password = admin_password_hash
                    admin.save(update_fields=['password'])
        except Exception:
            hospital.delete(force_drop=True)
            raise

        subscriptions.start_trial(hospital, email=contact_email or admin_email)
        events.publish('platform.hospital_provisioned', resource=hospital, domain=domain, plan=plan)
    return hospital, admin


def hospital_tables():
    '''Database tables that belong inside each hospital's schema.'''
    tenant_labels = {app.rsplit('.', 1)[-1] for app in settings.TENANT_APPS}
    return sorted(
        {
            model._meta.db_table
            for model in apps.get_models(include_auto_created=True)
            if model._meta.app_label in tenant_labels and model._meta.managed and not model._meta.proxy
        }
    )


def _columns(cursor, schema, table):
    cursor.execute(
        'SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s '
        'ORDER BY ordinal_position',
        [schema, table],
    )
    return [row[0] for row in cursor.fetchall()]


def copy_hospital_data(*, source_schema, target_schema, force=False):
    '''
    Replace the target hospital's data with a copy of the source schema's
    hospital tables. Used once to move a pre-multi-tenancy database (all data
    in "public") into its first hospital. Both schemas must be fully migrated.

    Returns {table: rows copied}.
    '''
    for schema in (source_schema, target_schema):
        if not (schema == get_public_schema_name() or SCHEMA_NAME.match(schema)):
            raise ValidationError(f'Invalid schema name: {schema}')

    tables = hospital_tables()
    with connection.cursor() as cursor:
        target_columns = {table: _columns(cursor, target_schema, table) for table in tables}
        source_columns = {table: _columns(cursor, source_schema, table) for table in tables}

        missing = [table for table in tables if not target_columns[table]]
        if missing:
            raise ValidationError(f'Target schema "{target_schema}" is missing tables: {", ".join(missing)}')
        mismatched = [
            table
            for table in tables
            if source_columns[table] and set(source_columns[table]) != set(target_columns[table])
        ]
        if mismatched:
            raise ValidationError(
                f'Column mismatch (migrate both schemas to the same version first): {", ".join(mismatched)}'
            )

        def target(table):
            return sql.Identifier(target_schema, table)

        cursor.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(target(User._meta.db_table)))
        if cursor.fetchone()[0] and not force:
            raise ValidationError(f'Hospital "{target_schema}" already has users; refusing to overwrite without force.')

        copied = {}
        with transaction.atomic():
            # Settle any checks pending from earlier work in this transaction (TRUNCATE
            # refuses tables with pending trigger events), then defer: Django's foreign
            # keys are DEFERRABLE, so tables can be filled in any order.
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute('SET CONSTRAINTS ALL DEFERRED')
            cursor.execute(sql.SQL('TRUNCATE {} CASCADE').format(sql.SQL(', ').join(map(target, tables))))

            for table in tables:
                if not source_columns[table]:
                    continue
                columns = sql.SQL(', ').join(map(sql.Identifier, source_columns[table]))
                cursor.execute(
                    sql.SQL('INSERT INTO {target} ({columns}) SELECT {columns} FROM {source}').format(
                        target=target(table), columns=columns, source=sql.Identifier(source_schema, table)
                    )
                )
                copied[table] = cursor.rowcount
                if 'id' in source_columns[table]:
                    # Continue id sequences after the copied rows
                    cursor.execute(
                        sql.SQL(
                            "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), "
                            'MAX(id) IS NOT NULL) FROM {}'
                        ).format(target(table)),
                        [f'"{target_schema}"."{table}"'],
                    )
    ContentType.objects.clear_cache()
    return copied
