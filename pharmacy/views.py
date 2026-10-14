from rest_framework import viewsets

from audit.mixins import AuditedReadMixin
from authentication.permissions import Role, allow_roles
from tenants.features import Feature, requires_feature

from .filters import DispenseTransactionFilter, DrugFilter
from .models import DispenseTransaction, Drug
from .serializers import DispenseTransactionSerializer, DrugSerializer


class DrugViewSet(viewsets.ModelViewSet):
    '''Filters: name (partial), low_stock=true.'''

    filterset_class = DrugFilter
    ordering_fields = ['name', 'quantity_in_stock']
    serializer_class = DrugSerializer
    queryset = Drug.objects.order_by('name')
    permission_classes = [
        requires_feature(Feature.PHARMACY),
        allow_roles(
            read=[Role.DOCTOR, Role.NURSE],
            write=[Role.PHARMACIST, Role.ADMIN],
        ),
    ]


class DispenseTransactionViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''Stock rules live in pharmacy.services.dispense. Filters: pharmacist, date_from, date_to.'''

    filterset_class = DispenseTransactionFilter
    ordering_fields = ['dispensed_at']
    serializer_class = DispenseTransactionSerializer
    queryset = (
        DispenseTransaction.objects.select_related('pharmacist__user')
        .prefetch_related('items__prescription__consultation__visit__patient__user')
        .order_by('-dispensed_at')
    )
    permission_classes = [requires_feature(Feature.PHARMACY), allow_roles(read=[Role.ADMIN], write=[Role.PHARMACIST])]
    # Dispensing already moved stock, so records are create-only (no edit/delete)
    http_method_names = ['get', 'post', 'head', 'options']
