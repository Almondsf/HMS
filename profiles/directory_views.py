'''Patient registry, staff directory and departments.'''

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.mixins import AuditedReadMixin
from authentication.models import User
from authentication.permissions import STAFF_ROLES, Role, allow_roles
from helpers.search import search
from tenants.features import Feature, requires_feature

from . import services
from .models import Department, PatientProfile
from .serializers import DepartmentSerializer, PatientSerializer, StaffSerializer

PATIENT_SEARCH_FIELDS = ['mrn', 'user__first_name', 'user__last_name', 'user__email', 'user__phone_number']
STAFF_SEARCH_FIELDS = ['first_name', 'last_name', 'email', 'phone_number']


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


class DepartmentViewSet(viewsets.ModelViewSet):
    '''Departments. Retire with is_active=false instead of deleting.'''

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [allow_roles(read=STAFF_ROLES, write=[Role.ADMIN])]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
