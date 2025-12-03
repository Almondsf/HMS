from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .models import Visit, Consultation
from .serializers import VisitSerializer, ConsultationSerializer


class VisitViewSet(viewsets.ModelViewSet):
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'receptionist':
            return Visit.objects.select_related('patient__user', 'assigned_doctor__user').all()

        
        if user.user_type == 'doctor':
             return Visit.objects.select_related('patient__user', 'assigned_doctor__user').filter(assigned_doctor__user=user)
        
        return Visit.objects.none()
    
    def perform_create(self, serializer):
        # Only receptionist can create visits
        if self.request.user.user_type != 'receptionist':
            raise PermissionDenied("Only receptionists can create visits")
        serializer.save()


class ConsultationViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'admin':
            return Consultation.objects.select_related('visit__patient__user', 'visit__assigned_doctor__user').all()
        
        if user.user_type == 'doctor':
            return Consultation.objects.select_related('visit__patient__user', 'visit__assigned_doctor__user')
        
        return Consultation.objects.none()
    
    def perform_create(self, serializer):
        user = self.request.user

        if user.user_type != 'doctor':
            raise PermissionDenied("Only doctors can create consultations")

        visit = serializer.validated_data['visit']

        if not visit.assigned_doctor:
            raise PermissionDenied(f"Visit {visit.id} has no assigned doctor")

        if not visit.assigned_doctor.user:
            raise PermissionDenied(f"Assigned doctor for visit {visit.id} has no linked user")

        if visit.assigned_doctor.user != user:
            raise PermissionDenied("You can only create consultations for your assigned visits")

        serializer.save()