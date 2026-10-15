import tempfile

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.http import FileResponse
from django.utils import timezone
from django_tenants.utils import get_public_schema_name
from rest_framework import generics, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.recorder import Category, record
from authentication.permissions import Role, allow_roles
from signup import services as signups
from signup.models import Signup
from subscriptions import services as subscriptions
from subscriptions.views import PaymentSerializer

from . import export, platform
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
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'schema_name', 'contact_email', 'domains__domain']
    ordering_fields = ['name', 'created_at', 'plan']
    ordering = ['name']

    def get_serializer_class(self):
        return HospitalProvisionSerializer if self.action == 'create' else PlatformHospitalSerializer

    def retrieve(self, request, *args, **kwargs):
        '''One hospital, with how much it uses the system and its payments.'''
        hospital = self.get_object()
        return Response({
            **PlatformHospitalSerializer(hospital).data,
            'usage': platform.usage(hospital),
            'payments': PaymentSerializer(hospital.subscription_payments.all()[:24], many=True).data,
        })  # fmt: skip

    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        '''Give extra days of access: a longer trial, or time while a payment is sorted out.'''
        data = ExtendSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        hospital = self.get_object()
        subscriptions.extend_access(hospital=hospital, by=request.user, **data.validated_data)
        return Response(PlatformHospitalSerializer(Hospital.objects.get(pk=hospital.pk)).data)

    @action(detail=True, methods=['post'], url_path='record-payment')
    def record_payment(self, request, pk=None):
        '''Record an offline payment (bank transfer): extends the subscription by one interval.'''
        data = ManualPaymentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        hospital = self.get_object()
        subscriptions.record_manual_payment(hospital=hospital, by=request.user, **data.validated_data)
        return Response(PlatformHospitalSerializer(Hospital.objects.get(pk=hospital.pk)).data)


class ExtendSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=90)
    reason = serializers.CharField(max_length=255)


class PlatformOverviewView(APIView):
    '''The business at a glance: hospitals, revenue, signups, and who needs attention.'''

    permission_classes = [IsPlatformOperator]

    def get(self, request):
        return Response(platform.overview())


class PlatformSignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signup
        fields = [
            'id', 'created_at', 'hospital_name', 'address', 'plan', 'first_name', 'last_name', 'email', 'phone',
            'status', 'error', 'verified_at', 'provisioning_started_at', 'completed_at', 'hospital',
            'terms_version', 'privacy_version', 'terms_accepted_at',
        ]  # fmt: skip


class PlatformSignupViewSet(viewsets.ReadOnlyModelViewSet):
    '''Everyone who signed up, and whether their hospital was created.'''

    queryset = Signup.objects.all()
    serializer_class = PlatformSignupSerializer
    permission_classes = [IsPlatformOperator]
    filter_backends = [SearchFilter]
    search_fields = ['hospital_name', 'address', 'email']

    def get_queryset(self):
        queryset = super().get_queryset()
        state = self.request.query_params.get('status')
        return queryset.filter(status=state) if state else queryset

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        '''Try again to create the hospital for a failed or stuck signup.'''
        signup = self.get_object()
        stuck = signup.status == Signup.Status.PROVISIONING and signups.stalled().filter(pk=signup.pk).exists()
        if signup.status != Signup.Status.FAILED and not stuck:
            raise ValidationError('Only failed or stuck signups can be retried.')
        if not signup.password_hash:
            raise ValidationError(
                'This signup is too old to retry (its password was deleted). Ask them to sign up again.'
            )
        signup.status, signup.error, signup.provisioning_started_at = Signup.Status.PROVISIONING, '', timezone.now()
        signup.save(update_fields=['status', 'error', 'provisioning_started_at', 'updated_at'])
        transaction.on_commit(lambda: signups.start_provisioning(signup.pk))
        return Response(PlatformSignupSerializer(signup).data)


class HospitalSettingsView(generics.RetrieveUpdateAPIView):
    '''The current hospital's own settings. Any signed-in user can read them; admins edit.'''

    serializer_class = HospitalSettingsSerializer
    permission_classes = [allow_roles(read=Role.values, write=[Role.ADMIN])]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return Hospital.objects.prefetch_related('domains').get(pk=connection.tenant.pk)


class ExportPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False)


class HospitalExportView(APIView):
    '''
    Download all of the hospital's records (ZIP of CSV files). Admins only,
    with their password: it is every patient's data in one file. Audited.
    '''

    permission_classes = [allow_roles(write=[Role.ADMIN])]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'export'

    def post(self, request):
        data = ExportPasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if not request.user.check_password(data.validated_data['password']):
            record('data.export_refused', Category.SECURITY, metadata={'reason': 'wrong password'})
            raise ValidationError({'password': 'Incorrect password.'})
        hospital = Hospital.objects.get(pk=connection.tenant.pk)
        archive = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
        counts = export.write_export(archive, hospital)
        archive.seek(0)
        record('data.exported', Category.SECURITY, metadata={'rows': sum(counts.values()), 'files': len(counts)})
        return FileResponse(
            archive, as_attachment=True, filename=export.filename(hospital), content_type='application/zip'
        )
