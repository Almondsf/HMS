import django_filters as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.mixins import AuditedReadMixin
from authentication.permissions import STAFF_ROLES, Role, allow_roles
from tenants.features import Feature, requires_feature

from . import services
from .models import Claim, Coverage, InsuranceProvider
from .serializers import (
    ClaimPaymentSerializer,
    ClaimResponseSerializer,
    ClaimSerializer,
    CoverageSerializer,
    InsuranceProviderSerializer,
)

INSURANCE = requires_feature(Feature.INSURANCE)
CLAIMS_STAFF = [Role.CASHIER, Role.ADMIN]


class InsuranceProviderViewSet(viewsets.ModelViewSet):
    '''HMOs, NHIA and other payers the hospital accepts. Retire with is_active=false.'''

    queryset = InsuranceProvider.objects.all()
    serializer_class = InsuranceProviderSerializer
    filterset_fields = ['kind', 'is_active']
    permission_classes = [INSURANCE, allow_roles(read=STAFF_ROLES, write=[Role.ADMIN])]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class CoverageViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''Patients' insurance memberships. Filters: patient, provider, is_active.'''

    serializer_class = CoverageSerializer
    filterset_fields = ['patient', 'provider', 'is_active']
    permission_classes = [
        INSURANCE,
        allow_roles(read=[Role.DOCTOR, Role.PATIENT], write=[Role.RECEPTIONIST, *CLAIMS_STAFF]),
    ]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        coverages = Coverage.objects.select_related('provider', 'patient__user')
        if self.request.user.user_type == Role.PATIENT:
            return coverages.filter(patient__user=self.request.user)
        return coverages


class ClaimFilter(filters.FilterSet):
    provider = filters.NumberFilter(field_name='coverage__provider')
    patient = filters.NumberFilter(field_name='invoice__patient')
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Claim
        fields = ['status', 'invoice']


class ClaimViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''
    Insurance claims: create (draft) -> submit -> respond (approve / reject) ->
    pay. Filters: status, provider, patient, invoice, date_from, date_to.
    '''

    serializer_class = ClaimSerializer
    filterset_class = ClaimFilter
    ordering_fields = ['created_at', 'claimed_amount']
    permission_classes = [INSURANCE, allow_roles(write=CLAIMS_STAFF)]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return Claim.objects.select_related('coverage__provider', 'invoice__patient__user')

    def _respond(self, claim):
        return Response(self.get_serializer(claim).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return self._respond(services.submit_claim(claim=self.get_object()))

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        '''Record the insurer's decision: approved_amount, or rejection_reason.'''
        data = ClaimResponseSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._respond(services.record_response(claim=self.get_object(), **data.validated_data))

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        '''The insurer paid: records an insurance payment on the invoice.'''
        data = ClaimPaymentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        claim = services.record_claim_payment(claim=self.get_object(), by=request.user, **data.validated_data)
        return self._respond(claim)

    @action(detail=True, methods=['get'])
    def document(self, request, pk=None):
        '''Claim details in the shape insurers ask for (member, ICD-10 diagnoses, itemised charges).'''
        return Response(services.claim_document(self.get_object()))

    @action(detail=False, methods=['get'])
    def outstanding(self, request):
        '''Money insurers still owe, by provider.'''
        return Response(services.outstanding_by_provider())
