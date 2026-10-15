'''API plumbing shared by every app.'''

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from django.http import JsonResponse
from rest_framework import exceptions, serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def api_exception_handler(exc, context):
    '''
    Services raise plain Django ValidationError so they stay usable outside
    the API (admin, management commands, tasks). Translate them to 400s here.
    '''
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, 'error_dict') else exc.messages
        exc = serializers.ValidationError(detail)
    if isinstance(exc, (exceptions.PermissionDenied, DjangoPermissionDenied)):
        _record_denied(exc, context)
    if isinstance(exc, ProtectedError):
        # e.g. deleting a drug that has been prescribed: keep history intact
        return Response(
            {'detail': 'This record is referenced by other records and cannot be deleted.'},
            status=status.HTTP_409_CONFLICT,
        )
    return drf_exception_handler(exc, context)


def _record_denied(exc, context):
    # Repeated denials from one account are an early sign of misuse
    from audit.recorder import Category, record

    request = context.get('request')
    record(
        'permission_denied',
        Category.SECURITY,
        metadata={
            'method': getattr(request, 'method', ''),
            'path': getattr(request, 'path', ''),
            'detail': str(exc),
        },
    )


class StandardPagination(PageNumberPagination):
    '''?page=N, and ?page_size=N up to 100.'''

    page_size_query_param = 'page_size'
    max_page_size = 100


def not_found(request, exception=None):
    '''JSON 404 for unknown URLs (Django's default is an HTML page).'''
    return JsonResponse({'detail': 'Not found.'}, status=404)


def server_error(request):
    '''JSON 500 carrying the request id, so support can find the logs.'''
    from audit.context import current_request_id

    return JsonResponse({'detail': 'Something went wrong on our side.', 'request_id': current_request_id()}, status=500)


def parse_date_param(params, name, default=None):
    """A YYYY-MM-DD query parameter as a date (400 on bad input, e.g. 2026-13-01)."""
    from django.utils.dateparse import parse_date

    raw = params.get(name)
    if not raw:
        return default
    try:
        value = parse_date(raw)
    except ValueError:  # well-formed but impossible dates raise
        value = None
    if value is None:
        raise exceptions.ValidationError({name: 'Use a valid date, YYYY-MM-DD.'})
    return value


def app_url(request, path):
    """
    A link into the web app for this hospital (emails, payment returns). The
    app is served at the hospital's own address unless FRONTEND_URL says
    otherwise (e.g. the Vite dev server: http://{subdomain}.localhost:5173).
    """
    from django.conf import settings
    from django.db import connection
    from django_tenants.utils import get_public_schema_name

    if connection.schema_name == get_public_schema_name():
        return platform_url(request, path)  # e.g. a platform operator's password reset
    host = request.get_host()
    if settings.FRONTEND_URL:
        base = settings.FRONTEND_URL.format(subdomain=host.split('.')[0], host=host)
    else:
        base = f'{request.scheme}://{host}'
    return f'{base.rstrip("/")}/{path.lstrip("/")}'


def platform_url(request, path):
    '''A link into the web app on the platform site (e.g. signup emails).'''
    from django.conf import settings

    if settings.FRONTEND_URL:
        base = settings.FRONTEND_URL.replace('{subdomain}.', '').format(host=request.get_host())
    else:
        base = f'{request.scheme}://{request.get_host()}'
    return f'{base.rstrip("/")}/{path.lstrip("/")}'


def hospital_url(request, address, path):
    '''A link into a hospital's web app from the platform site, e.g. after signup.'''
    from django.conf import settings

    if settings.FRONTEND_URL:
        base = settings.FRONTEND_URL.format(subdomain=address, host=request.get_host())
    else:
        base = f'{request.scheme}://{address}.{settings.TENANT_BASE_DOMAIN}'
    return f'{base.rstrip("/")}/{path.lstrip("/")}'
