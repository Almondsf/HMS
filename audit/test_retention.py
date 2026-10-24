import gzip
import os
import tempfile
from datetime import timedelta
from io import StringIO

from django.core.management import CommandError, call_command
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from helpers.testing import TenantAPITestCase

from .models import AuditEvent


class AuditRetentionTests(TenantAPITestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        old = timezone.now() - timedelta(days=800)
        for n in range(3):
            AuditEvent.objects.create(occurred_at=old, category='data_access', action='view', resource_id=str(n))
        self.recent = AuditEvent.objects.create(category='data_access', action='view', resource_id='recent')
        self.before = (timezone.localdate() - timedelta(days=400)).isoformat()

    def archive(self, *args):
        call_command(
            'archive_audit_log', '--before', self.before, '--output', self.folder.name,
            '--schema', self.tenant.schema_name, *args, stdout=StringIO(),
        )  # fmt: skip
        return os.path.join(self.folder.name, f'{self.tenant.schema_name}-audit-before-{self.before}.csv.gz')

    def test_archives_old_entries_and_keeps_them_unless_asked(self):
        path = self.archive()
        with gzip.open(path, 'rt', encoding='utf-8') as file:
            self.assertEqual(len(file.read().strip().splitlines()), 1 + 3)  # header + the three old entries
        self.assertEqual(AuditEvent.objects.filter(action='view').count(), 4)

    def test_delete_removes_only_what_was_archived(self):
        self.archive('--delete')
        self.assertEqual(
            list(AuditEvent.objects.filter(action='view').values_list('resource_id', flat=True)), ['recent']
        )
        archived = AuditEvent.objects.get(action='audit.archived')
        self.assertEqual((archived.metadata['rows'], archived.metadata['deleted']), (3, 3))

    def test_recent_entries_are_protected(self):
        self.before = (timezone.localdate() - timedelta(days=30)).isoformat()
        with self.assertRaisesMessage(CommandError, 'at least 365 days'):
            self.archive('--delete')

    def test_the_database_still_refuses_deletes_and_edits_outside_the_tool(self):
        table = AuditEvent._meta.db_table
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f'DELETE FROM {table} WHERE id = %s', [self.recent.pk])  # noqa: S608
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL hms.audit_retention_purge = 'on'")  # even with the switch: never edits
            cursor.execute(f"UPDATE {table} SET action = 'tampered' WHERE id = %s", [self.recent.pk])  # noqa: S608
        self.assertTrue(AuditEvent.objects.filter(pk=self.recent.pk, action='view').exists())
