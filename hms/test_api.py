import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import RequestFactory, override_settings
from django.utils import timezone
from rest_framework import status

from authentication.models import User
from clinical.models import Prescription, Visit
from helpers.api import server_error
from helpers.testing import TenantAPITestCase, make_consultation, make_user
from hms import spa
from pharmacy.models import Drug

Role = User.UserType


class VersioningTests(TenantAPITestCase):
    def setUp(self):
        self.client.force_authenticate(make_user(Role.ADMIN))

    def test_legacy_paths_still_work_and_point_to_v1(self):
        response = self.client.get('/api/visits/?page=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Deprecation'], 'true')
        self.assertEqual(response['Link'], '</api/v1/visits/>; rel="successor-version"')

        legacy_detail = self.client.get('/api/hospital/')
        self.assertEqual(legacy_detail.data['name'], 'Test Hospital')

    def test_current_paths_are_not_marked_deprecated(self):
        response = self.client.get('/api/v1/visits/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('Deprecation', response)


class ErrorFormatTests(TenantAPITestCase):
    def test_unknown_api_urls_return_json_404(self):
        response = self.client.get('/api/v1/nothing-here/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {'detail': 'Not found.'})

    def test_server_errors_return_json_with_request_id(self):
        response = server_error(RequestFactory().get('/api/v1/visits/'))
        self.assertEqual(response.status_code, 500)
        self.assertIn('request_id', json.loads(response.content))


class FilteringTests(TenantAPITestCase):
    def setUp(self):
        self.client.force_authenticate(make_user(Role.ADMIN))

    def ids(self, url, **params):
        return [item['id'] for item in self.client.get(url, params).data['results']]

    def test_visits_by_status_and_date(self):
        old, new = make_consultation().visit, make_consultation().visit
        Visit.objects.filter(pk=old.pk).update(
            visit_date=timezone.now() - timedelta(days=30), status=Visit.Status.COMPLETED
        )
        last_week = (timezone.localdate() - timedelta(days=7)).isoformat()

        self.assertEqual(self.ids('/api/v1/visits/', status='completed'), [old.id])
        self.assertEqual(self.ids('/api/v1/visits/', date_from=last_week), [new.id])
        self.assertEqual(self.ids('/api/v1/visits/', ordering='-visit_date'), [new.id, old.id])

    def test_low_stock_drugs(self):
        low = Drug.objects.create(name='Insulin', quantity_in_stock=2, reorder_level=5)
        Drug.objects.create(name='Paracetamol', quantity_in_stock=500, reorder_level=50)
        self.assertEqual(self.ids('/api/v1/pharmacy/drugs/', low_stock='true'), [low.id])
        self.assertEqual(len(self.ids('/api/v1/pharmacy/drugs/', name='para')), 1)

    def test_pending_prescriptions_queue(self):
        drug = Drug.objects.create(name='Amoxicillin', quantity_in_stock=100)
        consultation = make_consultation()

        def prescribe(quantity):
            return Prescription.objects.create(
                consultation=consultation, drug=drug, medication_name='Amoxicillin',
                dosage='500mg', frequency='TDS', duration='5 days', quantity=quantity,
            )  # fmt: skip

        untouched, partly, fully = prescribe(15), prescribe(15), prescribe(15)
        self.client.force_authenticate(make_user(Role.PHARMACIST))
        for prescription, quantity in ((partly, 5), (fully, 15)):
            self.client.post('/api/v1/pharmacy/dispense-transactions/', {
                'items': [{'prescription': prescription.id, 'drug': drug.id, 'quantity_dispensed': quantity}]
            }, format='json')  # fmt: skip

        self.assertEqual(sorted(self.ids('/api/v1/prescriptions/', pending='true')), sorted([untouched.id, partly.id]))
        self.assertEqual(self.ids('/api/v1/prescriptions/', pending='false'), [fully.id])

    def test_page_size_is_adjustable_but_capped(self):
        for _ in range(3):
            make_consultation()
        self.assertEqual(len(self.client.get('/api/v1/visits/', {'page_size': 2}).data['results']), 2)
        self.assertEqual(len(self.client.get('/api/v1/visits/', {'page_size': 1000}).data['results']), 3)


class WebAppTests(TenantAPITestCase):
    """Non-API paths serve the built web app, with runtime config injected."""

    def setUp(self):
        spa._index_html.cache_clear()
        self.addCleanup(spa._index_html.cache_clear)

    def test_app_routes_serve_index_with_config(self):
        with tempfile.TemporaryDirectory() as dist:
            Path(dist, 'index.html').write_text('<html><head><title>HMS</title></head><body></body></html>')
            with override_settings(FRONTEND_DIST=Path(dist), TENANT_BASE_DOMAIN='hms.example'):
                for path in ['/', '/queue', '/patients/12']:
                    with self.subTest(path=path):
                        response = self.client.get(path)
                        self.assertEqual(response.status_code, 200)
                        html = response.content.decode()
                        self.assertIn('window.__HMS_CONFIG__ = {"tenantBaseDomain": "hms.example", "apiUrl": ""}', html)
                        self.assertEqual(response['Cache-Control'], 'no-cache')

    def test_without_a_built_app_paths_go_to_the_api_docs(self):
        with tempfile.TemporaryDirectory() as empty, override_settings(FRONTEND_DIST=Path(empty)):
            response = self.client.get('/queue')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/api/docs/')
