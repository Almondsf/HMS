from django.db import connection
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name

HEALTH_PATH = '/api/health/'


class HealthCheckMiddleware:
    '''
    Answer health probes before hospital lookup and host validation: the
    platform probes by internal hostname, which maps to no hospital.
    '''

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            try:
                connection.ensure_connection()
            except Exception:
                return JsonResponse({'status': 'unavailable', 'database': 'down'}, status=503)
            return JsonResponse({'status': 'ok', 'database': 'up'})
        return self.get_response(request)


class HospitalMiddleware(TenantMainMiddleware):
    '''Routes each request to its hospital's schema by hostname.'''

    def no_tenant_found(self, request, hostname):
        return JsonResponse({'detail': 'No hospital is registered at this address.'}, status=404)

    def process_request(self, request):
        response = super().process_request(request)
        if response is not None:
            return response
        if request.tenant.schema_name != get_public_schema_name() and not request.tenant.is_active:
            return JsonResponse({'detail': "This hospital's account is suspended. Please contact support."}, status=403)
        return None
