from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.mixins import AuditedReadMixin
from authentication.permissions import Role, allow_roles
from tenants.features import Feature, requires_feature

from . import services
from .filters import AppointmentFilter
from .models import Appointment
from .serializers import AppointmentSerializer, CancellationSerializer

FRONT_DESK = [Role.ADMIN, Role.RECEPTIONIST]
FRONT_DESK_ONLY = [requires_feature(Feature.CLINICAL), allow_roles(write=FRONT_DESK)]


class AppointmentViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''
    Appointments. Front desk books, reschedules (PATCH starts_at or
    duration_minutes), checks in, cancels and marks no-shows. Doctors see
    their own schedule; patients see their own appointments.
    Filters: date, date_from, date_to, status, doctor, patient, department.
    '''

    serializer_class = AppointmentSerializer
    filterset_class = AppointmentFilter
    ordering_fields = ['starts_at']
    permission_classes = [
        requires_feature(Feature.CLINICAL),
        allow_roles(read=[Role.DOCTOR, Role.NURSE, Role.PATIENT], write=FRONT_DESK),
    ]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        appointments = Appointment.objects.select_related('patient__user', 'doctor__user')
        user = self.request.user
        if user.user_type == Role.DOCTOR:
            return appointments.filter(doctor__user=user)
        if user.user_type == Role.PATIENT:
            return appointments.filter(patient__user=user)
        return appointments

    def _act(self, service, **kwargs):
        appointment = service(appointment=self.get_object(), **kwargs)
        return Response(self.get_serializer(appointment).data)

    @action(detail=True, methods=['post'], url_path='check-in', permission_classes=FRONT_DESK_ONLY)
    def check_in(self, request, pk=None):
        '''Patient arrived: opens a visit and puts them in the doctor's queue.'''
        return self._act(services.check_in)

    @action(detail=True, methods=['post'], permission_classes=FRONT_DESK_ONLY)
    def cancel(self, request, pk=None):
        reason = CancellationSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        return self._act(services.cancel_appointment, reason=reason.validated_data['reason'])

    @action(detail=True, methods=['post'], url_path='no-show', permission_classes=FRONT_DESK_ONLY)
    def no_show(self, request, pk=None):
        return self._act(services.mark_no_show)
