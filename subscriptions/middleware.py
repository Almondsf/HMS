from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django_tenants.utils import get_public_schema_name

from .models import Subscription

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
# Still usable when read-only: signing in and out, passwords, paying, and taking your data away
ALWAYS_ALLOWED = (
    '/api/v1/auth/',
    '/api/auth/',
    '/api/v1/subscription/',
    '/api/v1/hospital/export/',
    '/api/v1/notifications/',
    f'/{settings.ADMIN_URL}',  # wherever ADMIN_URL puts the admin
)


class SubscriptionAccessMiddleware:
    '''
    A hospital past its grace period becomes read-only: every record stays
    viewable (patient care must not stop), but nothing new can be created
    until the subscription is paid. Changes are refused with 402.
    '''

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in SAFE_METHODS or connection.schema_name == get_public_schema_name():
            return self.get_response(request)
        if request.path.startswith(ALWAYS_ALLOWED):
            return self.get_response(request)
        subscription = Subscription.objects.filter(hospital_id=connection.tenant.pk).first()
        if subscription is not None and subscription.access() == Subscription.Access.READ_ONLY:
            return JsonResponse(
                {
                    'detail': "This hospital's subscription has lapsed, so records are read-only. "
                    'An administrator can renew it under Subscription.',
                    'code': 'subscription_lapsed',
                },
                status=402,
            )
        return self.get_response(request)
