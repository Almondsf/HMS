from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework import generics, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from authentication.permissions import Role, allow_roles
from subscriptions import services as subscriptions

from .models import Hospital
from .serializers import (
    HospitalProvisionSerializer,
    HospitalSettingsSerializer,
    ManualPaymentSerializer,
    PlatformHospitalSerializer,
)


class IsPlatformOperator(BasePermission):
    '''Superusers of the platform site itself (not hospital admins).'''

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_superuser and connection.schema_name == get_public_schema_name()
        )


class HospitalViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    '''
    Platform operators manage hospitals. Creating one provisions its database
    schema and first admin (takes a few seconds). Suspend with is_active=false;
    hospitals are never deleted through the API.
    '''

    queryset = Hospital.objects.exclude(schema_name=get_public_schema_name()).prefetch_related('domains')
    permission_classes = [IsPlatformOperator]

    def get_serializer_class(self):
        return HospitalProvisionSerializer if self.action == 'create' else PlatformHospitalSerializer

    @action(detail=True, methods=['post'], url_path='record-payment')
    def record_payment(self, request, pk=None):
        '''Record an offline payment (bank transfer): extends the subscription by one interval.'''
        data = ManualPaymentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        hospital = self.get_object()
        subscriptions.record_manual_payment(hospital=hospital, by=request.user, **data.validated_data)
        return Response(PlatformHospitalSerializer(Hospital.objects.get(pk=hospital.pk)).data)


class HospitalSettingsView(generics.RetrieveUpdateAPIView):
    '''The current hospital's own settings. Any signed-in user can read them; admins edit.'''

    serializer_class = HospitalSettingsSerializer
    permission_classes = [allow_roles(read=Role.values, write=[Role.ADMIN])]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return Hospital.objects.prefetch_related('domains').get(pk=connection.tenant.pk)
