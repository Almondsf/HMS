from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from authentication.permissions import Role, allow_roles
from .models import Visit, Consultation
from .serializers import VisitSerializer, VisitSummarySerializer, ConsultationSerializer

# Clinical records are never hard-deleted through the API (no DELETE).
CLINICAL_RECORD_METHODS = ['get', 'post', 'put', 'patch', 'head', 'options']


class VisitViewSet(viewsets.ModelViewSet):
    permission_classes = [allow_roles(
        read=[Role.DOCTOR, Role.NURSE, Role.PATIENT],
        write=[Role.ADMIN, Role.RECEPTIONIST],
    )]
    http_method_names = CLINICAL_RECORD_METHODS

    def get_queryset(self):
        user = self.request.user
        visits = Visit.objects.select_related('patient__user', 'assigned_doctor__user')

        if user.is_superuser or user.user_type in (Role.ADMIN, Role.RECEPTIONIST, Role.NURSE):
            return visits.all()

        if user.user_type == Role.DOCTOR:
            return visits.filter(assigned_doctor__user=user)

        if user.user_type == Role.PATIENT:
            return visits.filter(patient__user=user)

        return Visit.objects.none()

    def get_serializer_class(self):
        # Front desk manages visits but doesn't need the clinical notes
        if self.request.user.user_type == Role.RECEPTIONIST:
            return VisitSummarySerializer
        return VisitSerializer


class ConsultationViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultationSerializer
    permission_classes = [allow_roles(
        read=[Role.ADMIN, Role.PATIENT],
        write=[Role.DOCTOR],
    )]
    http_method_names = CLINICAL_RECORD_METHODS

    def get_queryset(self):
        user = self.request.user
        consultations = Consultation.objects.select_related(
            'visit__patient__user', 'visit__assigned_doctor__user'
        )

        if user.is_superuser or user.user_type == Role.ADMIN:
            return consultations.all()

        if user.user_type == Role.DOCTOR:
            return consultations.filter(visit__assigned_doctor__user=user)

        if user.user_type == Role.PATIENT:
            return consultations.filter(visit__patient__user=user)

        return Consultation.objects.none()

    def _check_assigned_doctor(self, serializer):
        # Also applied on update, so a doctor can't move a consultation onto someone else's visit
        visit = serializer.validated_data.get('visit')
        if visit and visit.assigned_doctor.user_id != self.request.user.id:
            raise PermissionDenied("You can only record consultations for your assigned visits")

    def perform_create(self, serializer):
        if self.request.user.user_type != Role.DOCTOR:
            raise PermissionDenied("Only doctors can create consultations")
        self._check_assigned_doctor(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_assigned_doctor(serializer)
        serializer.save()
