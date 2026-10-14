import re

CURRENT_VERSION = 'v1'

# First path segments of the API before it was versioned
LEGACY_API_SECTIONS = {
    'auth', 'hospital', 'create-profile', 'visits', 'consultations', 'prescriptions', 'patients',
    'staff', 'departments', 'pharmacy', 'lab', 'audit', 'platform', 'queue', 'appointments', 'vitals',
}  # fmt: skip

_LEGACY_PATH = re.compile(r'^/api/(?P<section>[a-z-]+)(?P<rest>/.*)?$')


class LegacyApiPathMiddleware:
    '''
    Keep pre-versioning clients working: /api/visits/ is served as
    /api/v1/visits/, with headers telling clients to move (RFC 8594).
    '''

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        match = _LEGACY_PATH.match(request.path_info)
        if not (match and match['section'] in LEGACY_API_SECTIONS):
            return self.get_response(request)

        successor = f"/api/{CURRENT_VERSION}/{match['section']}{match['rest'] or '/'}"
        request.path_info = successor
        response = self.get_response(request)
        response['Deprecation'] = 'true'
        response['Link'] = f'<{successor}>; rel="successor-version"'
        return response
