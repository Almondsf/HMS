'''API plumbing shared by every app.'''

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from rest_framework import exceptions, serializers, status
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
    record('permission_denied', Category.SECURITY, metadata={
        'method': getattr(request, 'method', ''),
        'path': getattr(request, 'path', ''),
        'detail': str(exc),
    })
