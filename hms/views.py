from django.db import connection
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    '''Liveness/readiness probe for the hosting platform and uptime monitors.'''
    try:
        connection.ensure_connection()
    except Exception:
        return Response({'status': 'unavailable', 'database': 'down'}, status=503)
    return Response({'status': 'ok', 'database': 'up'})
