from io import StringIO

from django.contrib.admin.sites import site
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status

from authentication.models import User
from helpers.testing import SchemaRestoringAPIClient

from .models import LegalDocument


class LegalDocumentTests(TestCase):
    def setUp(self):
        cache.clear()
        with schema_context('public'):
            call_command('setup_platform', 'platform.localhost', stdout=StringIO())
        self.client = SchemaRestoringAPIClient(HTTP_HOST='platform.localhost')

    def test_drafts_are_served_and_marked_as_drafts(self):
        for kind in ('terms', 'privacy'):
            data = self.client.get(f'/api/v1/legal/{kind}/').data
            self.assertEqual(data['version'], 'draft-1')
            self.assertTrue(data['is_draft'])
            self.assertIn('Nigeria', data['body'])
        self.assertEqual(self.client.get('/api/v1/legal/cookies/').status_code, status.HTTP_404_NOT_FOUND)

    def test_newest_published_version_is_current(self):
        LegalDocument.objects.create(kind='terms', version='2026-11-01', body='# Terms\n\nFinal.', is_draft=False)
        self.assertEqual(self.client.get('/api/v1/legal/terms/').data['version'], 'draft-1')  # not published yet
        LegalDocument.objects.filter(version='2026-11-01').update(published_at=timezone.now())
        data = self.client.get('/api/v1/legal/terms/').data
        self.assertEqual((data['version'], data['is_draft']), ('2026-11-01', False))

    def test_published_versions_are_locked_in_the_admin(self):
        with schema_context('public'):
            request = RequestFactory().get('/')
            request.user = User(is_superuser=True, is_staff=True, is_active=True)
            admin = site._registry[LegalDocument]
            published = LegalDocument.current('terms')
            unpublished = LegalDocument(kind='terms', version='next', body='x')
            self.assertFalse(admin.has_change_permission(request, published))
            self.assertTrue(admin.has_change_permission(request, unpublished))
