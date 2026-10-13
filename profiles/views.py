# profile/views.py
from rest_framework.generics import CreateAPIView
from authentication.permissions import Role, allow_roles
from profiles.serializers import (
    PatientSerializer, DoctorSerializer, LabTechSerializer,
    PharmacistSerializer, ReceptionistSerializer
)
from .models import PatientProfile, DoctorProfile, LabTechProfile, PharmacistProfile, ReceptionistProfile

# Front desk registers patients; only admins create staff accounts.
CanRegisterPatients = allow_roles(write=[Role.ADMIN, Role.RECEPTIONIST])
CanRegisterStaff = allow_roles(write=[Role.ADMIN])


class patientView(CreateAPIView):
    permission_classes = [CanRegisterPatients]
    serializer_class = PatientSerializer
    queryset = PatientProfile.objects.all()

class doctorView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = DoctorSerializer
    queryset = DoctorProfile.objects.all()

class labTechView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = LabTechSerializer
    queryset = LabTechProfile.objects.all()

class pharmacistView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = PharmacistSerializer
    queryset = PharmacistProfile.objects.all()

class receptionistView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = ReceptionistSerializer
    queryset = ReceptionistProfile.objects.all()
