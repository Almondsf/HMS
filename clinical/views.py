from rest_framework import viewsets

from audit.mixins import AuditedReadMixin
from authentication.permissions import Role, allow_roles

from . import services
from .models import Consultation, Prescription, Visit
from .serializers import ConsultationSerializer, PrescriptionDetailSerializer, VisitSerializer, VisitSummarySerializer

# Clinical records are never hard-deleted through the API (no DELETE).
CLINICAL_RECORD_METHODS = ['get', 'post', 'put', 'patch', 'head', 'options']

CONSULTATION_PREFETCH = ['prescriptions__drug', 'lab_orders__results__test', 'lab_orders__results__labtech__user']


class VisitViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    permission_classes = [
        allow_roles(
            read=[Role.DOCTOR, Role.NURSE, Role.PATIENT],
            write=[Role.ADMIN, Role.RECEPTIONIST],
        )
    ]
    http_method_names = CLINICAL_RECORD_METHODS

    def get_queryset(self):
        user = self.request.user
        visits = Visit.objects.select_related('patient__user', 'assigned_doctor__user')

        if user.user_type == Role.RECEPTIONIST:
            return visits.all()

        visits = visits.prefetch_related(*(f'consultations__{path}' for path in CONSULTATION_PREFETCH))

        if user.is_superuser or user.user_type in (Role.ADMIN, Role.NURSE):
            return visits.all()

        if user.user_type == Role.DOCTOR:
            return visits.filter(assigned_doctor__user=user)

        if user.user_type == Role.PATIENT:
            return visits.filter(patient__user=user)

        return Visit.objects.none()

    def perform_create(self, serializer):
        services.open_visit(serializer)

    def get_serializer_class(self):
        # Front desk manages visits but doesn't need the clinical notes
        # (getattr: API schema generation runs this with an anonymous user)
        if getattr(self.request.user, 'user_type', None) == Role.RECEPTIONIST:
            return VisitSummarySerializer
        return VisitSerializer


class ConsultationViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''Creation rules (assigned doctor only) live in clinical.services.record_consultation.'''

    serializer_class = ConsultationSerializer
    permission_classes = [
        allow_roles(
            read=[Role.ADMIN, Role.PATIENT],
            write=[Role.DOCTOR],
        )
    ]
    http_method_names = CLINICAL_RECORD_METHODS

    def get_queryset(self):
        user = self.request.user
        consultations = Consultation.objects.select_related(
            'visit__patient__user', 'visit__assigned_doctor__user'
        ).prefetch_related(*CONSULTATION_PREFETCH)

        if user.is_superuser or user.user_type == Role.ADMIN:
            return consultations.all()

        if user.user_type == Role.DOCTOR:
            return consultations.filter(visit__assigned_doctor__user=user)

        if user.user_type == Role.PATIENT:
            return consultations.filter(visit__patient__user=user)

        return Consultation.objects.none()


class PrescriptionViewSet(AuditedReadMixin, viewsets.ReadOnlyModelViewSet):
    '''
    Prescriptions across consultations: the pharmacy's work queue.
    Filter with ?patient=<patient profile id> or ?consultation=<id>.
    '''

    serializer_class = PrescriptionDetailSerializer
    permission_classes = [allow_roles(read=[Role.PHARMACIST, Role.DOCTOR, Role.PATIENT, Role.ADMIN])]

    def get_queryset(self):
        user = self.request.user
        prescriptions = Prescription.objects.select_related(
            'drug', 'consultation__visit__patient__user', 'consultation__visit__assigned_doctor__user'
        ).order_by('-created_at')

        if user.user_type == Role.DOCTOR:
            prescriptions = prescriptions.filter(consultation__visit__assigned_doctor__user=user)
        elif user.user_type == Role.PATIENT:
            prescriptions = prescriptions.filter(consultation__visit__patient__user=user)

        params = self.request.query_params
        if 'patient' in params:
            prescriptions = prescriptions.filter(consultation__visit__patient_id=params['patient'])
        if 'consultation' in params:
            prescriptions = prescriptions.filter(consultation_id=params['consultation'])
        return prescriptions
