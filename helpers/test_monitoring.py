from django.test import SimpleTestCase

from helpers.monitoring import _scrub


class SentryScrubbingTests(SimpleTestCase):
    '''Errors may reach Sentry; patient data must not.'''

    def test_request_details_that_could_hold_patient_data_are_removed(self):
        event = {
            'request': {
                'url': 'https://stlukes.hms.app/api/v1/patients/?search=ada+obi',
                'query_string': 'search=ada+obi',
                'data': {'user': {'first_name': 'Ada', 'allergies': 'Penicillin'}},
                'cookies': {'hms_refresh': 'secret'},
                'headers': {'Authorization': 'Bearer secret', 'User-Agent': 'Chrome', 'Cookie': 'x=y'},
            },
            'breadcrumbs': {'values': [{'category': 'http', 'data': {'url': '/api/v1/patients/?search=obi'}}]},
        }

        scrubbed = _scrub(event, hint={})
        request = scrubbed['request']

        self.assertEqual(request['url'], 'https://stlukes.hms.app/api/v1/patients/')
        self.assertEqual(request['query_string'], '')
        self.assertNotIn('data', request)
        self.assertNotIn('cookies', request)
        self.assertEqual(request['headers'], {'User-Agent': 'Chrome'})
        self.assertEqual(scrubbed['breadcrumbs']['values'][0]['data']['url'], '/api/v1/patients/')
        self.assertNotIn('Ada', str(scrubbed))
