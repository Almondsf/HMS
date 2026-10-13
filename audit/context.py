'''Per-request context (request id, client, user) available to audit and logging code.'''

import re
import uuid
from contextvars import ContextVar

from django.conf import settings

_current_request = ContextVar('audit_request', default=None)
_request_id = ContextVar('request_id', default='')

_VALID_REQUEST_ID = re.compile(r'^[A-Za-z0-9._-]{8,64}$')


class AuditContextMiddleware:
    '''
    Tags every request with an id (honouring a sane incoming X-Request-ID from
    the proxy) and echoes it in the response, so a support ticket, a log line
    and an audit event can all be tied together.
    '''

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get('X-Request-ID', '')
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request_token = _current_request.set(request)
        id_token = _request_id.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            _current_request.reset(request_token)
            _request_id.reset(id_token)
        response['X-Request-ID'] = request_id
        return response


def current_request():
    return _current_request.get()


def current_request_id():
    return _request_id.get()


def current_user():
    '''The authenticated user, if any. DRF copies its user onto the Django request.'''
    request = current_request()
    user = getattr(request, 'user', None)
    return user if user is not None and user.is_authenticated else None


def client_ip(request):
    if settings.AUDIT_TRUST_X_FORWARDED_FOR:
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
