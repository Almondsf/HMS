from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.mixins import AuditedReadMixin
from authentication.permissions import Role, allow_roles
from tenants.features import Feature, requires_feature

from . import services
from .filters import ConsultationFilter, PrescriptionFilter, VisitFilter, VitalSignsFilter
from .models import Consultation, Prescription, Visit, VitalSigns
from .serializers import (
    ConsultationSerializer,
    PrescriptionDetailSerializer,
    QueueEntrySerializer,
    TriageSerializer,
    VisitSerializer,
    VisitSummarySerializer,
    VitalSignsSerializer,
)

# Clinical records are never hard-deleted through the API (no DELETE).
CLINICAL_RECORD_METHODS = ['get', 'post', 'put', 'patch', 'head', 'options']

BASE_VISIT_PERMISSIONS = [requires_feature(Feature.CLINICAL)]

VISIT_PREFETCH = ['vitals__recorded_by']

CONSULTATION_PREFETCH = ['prescriptions__drug', 'lab_orders__results__test', 'lab_orders__results__labtech__user']


class VisitViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''Filters: status, patient, assigned_doctor, date_from, date_to. Sort with ?ordering=-visit_date.'''

    filterset_class = VisitFilter
    ordering_fields = ['visit_date', 'status']
    permission_classes = [
        requires_feature(Feature.CLINICAL),
        allow_roles(
            read=[Role.DOCTOR, Role.NURSE, Role.PATIENT],
            write=[Role.ADMIN, Role.RECEPTIONIST],
        ),
    ]
    http_method_names = CLINICAL_RECORD_METHODS

    def get_queryset(self):
        user = self.request.user
        visits = Visit.objects.select_related('patient__user', 'assigned_doctor__user')

        if user.user_type == Role.RECEPTIONIST:
            return visits.all()

        visits = visits.prefetch_related(*VISIT_PREFETCH, *(f'consultations__{path}' for path in CONSULTATION_PREFETCH))

        if user.is_superuser or user.user_type in (Role.ADMIN, Role.NURSE):
            return visits.all()

        if user.user_type == Role.DOCTOR:
            return visits.filter(assigned_doctor__user=user)

        if user.user_type == Role.PATIENT:
            return visits.filter(patient__user=user)

        return Visit.objects.none()

    def perform_create(self, serializer):
        serializer.instance = services.open_visit(**serializer.validated_data)

    def _transition(self, service, **kwargs):
        visit = service(visit=self.get_object(), **kwargs)
        return Response(self.get_serializer(visit).data)

    @action(
        detail=True, methods=['post'], permission_classes=[*BASE_VISIT_PERMISSIONS, allow_roles(write=[Role.DOCTOR])]
    )
    def start(self, request, pk=None):
        '''Doctor calls the patient in: waiting -> in consultation.'''
        return self._transition(services.start_visit, by=request.user)

    @action(
        detail=True, methods=['post'], permission_classes=[*BASE_VISIT_PERMISSIONS, allow_roles(write=[Role.DOCTOR])]
    )
    def complete(self, request, pk=None):
        return self._transition(services.complete_visit, by=request.user)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[*BASE_VISIT_PERMISSIONS, allow_roles(write=[Role.ADMIN, Role.RECEPTIONIST])],
    )
    def cancel(self, request, pk=None):
        '''Front desk: the patient left before being seen.'''
        return self._transition(services.cancel_visit)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[*BASE_VISIT_PERMISSIONS, allow_roles(write=[Role.NURSE, Role.DOCTOR])],
    )
    def triage(self, request, pk=None):
        '''Set the patient's priority in the queue (emergency, urgent, standard, non_urgent).'''
        data = TriageSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._transition(
            services.triage,
            by=request.user,
            level=data.validated_data['triage_level'],
            notes=data.validated_data['triage_notes'],
        )

    def get_serializer_class(self):
        # Front desk manages visits but doesn't need the clinical notes
        # (getattr: API schema generation runs this with an anonymous user)
        if getattr(self.request.user, 'user_type', None) == Role.RECEPTIONIST:
            return VisitSummarySerializer
        return VisitSerializer


class ConsultationViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''
    Creation rules (assigned doctor only) live in clinical.services.record_consultation.
    Filters: visit, patient, date_from, date_to.
    '''

    filterset_class = ConsultationFilter
    ordering_fields = ['created_at', 'follow_up_date']
    serializer_class = ConsultationSerializer
    permission_classes = [
        requires_feature(Feature.CLINICAL),
        allow_roles(
            read=[Role.ADMIN, Role.PATIENT],
            write=[Role.DOCTOR],
        ),
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
    Filters: patient, consultation, drug, pending=true (units still to dispense).
    '''

    filterset_class = PrescriptionFilter
    ordering_fields = ['created_at']
    serializer_class = PrescriptionDetailSerializer
    permission_classes = [
        requires_feature(Feature.CLINICAL),
        allow_roles(read=[Role.PHARMACIST, Role.DOCTOR, Role.PATIENT, Role.ADMIN]),
    ]

    def get_queryset(self):
        user = self.request.user
        prescriptions = Prescription.objects.select_related(
            'drug', 'consultation__visit__patient__user', 'consultation__visit__assigned_doctor__user'
        ).order_by('-created_at')

        if user.user_type == Role.DOCTOR:
            prescriptions = prescriptions.filter(consultation__visit__assigned_doctor__user=user)
        elif user.user_type == Role.PATIENT:
            prescriptions = prescriptions.filter(consultation__visit__patient__user=user)
        return prescriptions


class QueueView(generics.ListAPIView):
    '''
    Today's queue: patients waiting or in consultation, in order of arrival.
    Doctors see their own queue; front desk and nurses can filter ?doctor=<id>.
    '''

    serializer_class = QueueEntrySerializer
    pagination_class = None
    filter_backends = []
    permission_classes = [
        requires_feature(Feature.CLINICAL),
        allow_roles(read=[Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN]),
    ]

    def get_queryset(self):
        visits = Visit.objects.filter(
            status__in=Visit.QUEUE_STATUSES, visit_date__date=timezone.localdate()
        ).select_related('patient__user', 'assigned_doctor__user', 'appointment')
        user = self.request.user
        if user.user_type == Role.DOCTOR:
            visits = visits.filter(assigned_doctor__user=user)
        elif 'doctor' in self.request.query_params:
            visits = visits.filter(assigned_doctor=self.request.query_params['doctor'])
        # Patients already with the doctor first, then the waiting line by
        # triage priority (emergencies first) and arrival time
        in_room_first = Case(
            When(status=Visit.Status.IN_PROGRESS, then=Value(0)), default=Value(1), output_field=IntegerField()
        )
        priority = Case(
            *(When(triage_level=level, then=Value(rank)) for level, rank in Visit.TRIAGE_RANK.items()),
            default=Value(Visit.TRIAGE_RANK[Visit.Triage.STANDARD]),
            output_field=IntegerField(),
        )
        return visits.order_by(in_room_first, priority, 'visit_date')

    def list(self, request, *args, **kwargs):
        visits = list(self.get_queryset())
        position = 0
        for visit in visits:
            # Position counts only those still waiting; whoever is in the room has none
            if visit.status == Visit.Status.WAITING:
                position += 1
                visit.position = position
            else:
                visit.position = None
        serializer = self.get_serializer(
            visits, many=True, context={**self.get_serializer_context(), 'now': timezone.now()}
        )
        return Response(serializer.data)


class VitalSignsViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''
    Vital signs. Nurses record them for any visit, doctors for their own
    patients. Observations are never edited: record a new set to correct one.
    Filters: visit, patient (for charting over time).
    '''

    serializer_class = VitalSignsSerializer
    filterset_class = VitalSignsFilter
    ordering_fields = ['recorded_at']
    permission_classes = [
        requires_feature(Feature.CLINICAL),
        allow_roles(read=[Role.ADMIN, Role.PATIENT], write=[Role.NURSE, Role.DOCTOR]),
    ]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        vitals = VitalSigns.objects.select_related('visit', 'recorded_by')
        user = self.request.user
        if user.user_type == Role.DOCTOR:
            return vitals.filter(visit__assigned_doctor__user=user)
        if user.user_type == Role.PATIENT:
            return vitals.filter(visit__patient__user=user)
        return vitals
