'''Patient registry, staff directory and departments.'''

from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from audit.mixins import AuditedReadMixin
from authentication import password_reset, two_factor
from authentication.models import User
from authentication.permissions import STAFF_ROLES, Role, allow_roles
from helpers.search import search
from tenants.features import Feature, requires_feature

from . import patient_import, services
from .models import Department, PatientProfile
from .serializers import DepartmentSerializer, PatientSerializer, StaffSerializer

PATIENT_SEARCH_FIELDS = ['mrn', 'user__first_name', 'user__last_name', 'user__email', 'user__phone_number']
STAFF_SEARCH_FIELDS = ['first_name', 'last_name', 'email', 'phone_number']


class ImportOptionsSerializer(serializers.Serializer):
    file = serializers.FileField()
    dry_run = serializers.BooleanField(default=True)
    skip_invalid = serializers.BooleanField(default=False)


class PatientViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''
    The patient registry. Search with ?search=<name, MRN, phone or email>.
    Front desk registers and updates patients; clinical staff look them up;
    patients see only their own record.
    '''

    serializer_class = PatientSerializer
    filterset_fields = ['assigned_doctor', 'blood_group', 'genotype']
    ordering_fields = ['mrn', 'user__last_name']
    permission_classes = [
        requires_feature(Feature.CLINICAL),
        allow_roles(
            read=[Role.DOCTOR, Role.NURSE, Role.LAB_TECHNICIAN, Role.PHARMACIST, Role.PATIENT],
            write=[Role.ADMIN, Role.RECEPTIONIST],
        ),
    ]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        patients = PatientProfile.objects.select_related('user', 'assigned_doctor__user').order_by('mrn')
        if self.request.user.user_type == Role.PATIENT:
            return patients.filter(user=self.request.user)
        return search(patients, self.request.query_params.get('search'), PATIENT_SEARCH_FIELDS)

    @action(detail=False, methods=['get'], url_path='import-template')
    def import_template(self, request):
        '''The spreadsheet columns for importing patients (CSV; opens in Excel).'''
        response = HttpResponse(patient_import.template_csv(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="patients-import-template.csv"'
        return response

    @swagger_auto_schema(request_body=ImportOptionsSerializer, responses={200: 'Import summary'})
    @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser])
    def import_patients(self, request):
        '''
        Import patients from a CSV or Excel file. With dry_run=true (the
        default) nothing is saved: the response lists problems by row. Then
        send dry_run=false to save, with skip_invalid=true to leave out the
        rows that have problems.
        '''
        options = ImportOptionsSerializer(data=request.data)
        options.is_valid(raise_exception=True)
        try:
            result = patient_import.run_import(
                options.validated_data['file'],
                commit=not options.validated_data['dry_run'],
                skip_invalid=options.validated_data['skip_invalid'],
            )
        except patient_import.ImportFileError as exc:
            return Response({'file': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class StaffViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    Staff directory, e.g. ?role=doctor to pick who to assign a visit to.
    Filters: role, department, search, is_active. Admins can deactivate or
    reactivate accounts; deactivating signs the person out everywhere.
    '''

    serializer_class = StaffSerializer
    permission_classes = [allow_roles(read=STAFF_ROLES)]

    def get_queryset(self):
        params = self.request.query_params
        staff = (
            User.objects.exclude(user_type=Role.PATIENT)
            .select_related('doctorprofile__department', 'nurseprofile__department')
            .order_by('last_name', 'first_name')
        )
        if 'role' in params:
            staff = staff.filter(user_type=params['role'])
        if 'department' in params:
            staff = staff.filter(doctorprofile__department=params['department']) | staff.filter(
                nurseprofile__department=params['department']
            )
        if 'is_active' in params:
            staff = staff.filter(is_active=params['is_active'].lower() in ('1', 'true', 'yes'))
        return search(staff, params.get('search'), STAFF_SEARCH_FIELDS)

    def _set_active(self, request, active):
        staff_user = self.get_object()
        services.set_staff_active(staff_user=staff_user, active=active, by=request.user)
        return Response(self.get_serializer(staff_user).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[allow_roles(write=[Role.ADMIN])])
    def deactivate(self, request, pk=None):
        return self._set_active(request, active=False)

    @action(detail=True, methods=['post'], permission_classes=[allow_roles(write=[Role.ADMIN])])
    def activate(self, request, pk=None):
        return self._set_active(request, active=True)

    @action(
        detail=True, methods=['post'], url_path='reset-password', permission_classes=[allow_roles(write=[Role.ADMIN])]
    )
    def reset_password(self, request, pk=None):
        '''Issue a temporary password (shown once); they must change it at next sign-in.'''
        password = password_reset.reset_by_admin(user=self.get_object(), by=request.user)
        return Response({'temporary_password': password}, status=status.HTTP_200_OK)

    @action(
        detail=True, methods=['post'], url_path='reset-two-factor', permission_classes=[allow_roles(write=[Role.ADMIN])]
    )
    def reset_two_factor(self, request, pk=None):
        '''Lost phone: remove their two-factor sign-in; they set it up again at next sign-in.'''
        staff = self.get_object()
        if staff.pk == request.user.pk:
            raise PermissionDenied('Use your own two-factor settings to change your phone.')
        two_factor.reset(staff, by=request.user)
        return Response(two_factor.status(staff))


class DepartmentViewSet(viewsets.ModelViewSet):
    '''Departments. Retire with is_active=false instead of deleting.'''

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [allow_roles(read=STAFF_ROLES, write=[Role.ADMIN])]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
