'''Registration endpoints (/api/create-profile/<role>/). Patients can also be registered at /api/patients/.'''

from rest_framework.generics import CreateAPIView

from authentication.permissions import Role, allow_roles
from profiles.serializers import (
    DoctorSerializer,
    LabTechSerializer,
    NurseSerializer,
    PatientSerializer,
    PharmacistSerializer,
    ReceptionistSerializer,
)

from .models import (
    DoctorProfile,
    LabTechProfile,
    NurseProfile,
    PatientProfile,
    PharmacistProfile,
    ReceptionistProfile,
)

# Front desk registers patients; only admins create staff accounts.
CanRegisterPatients = allow_roles(write=[Role.ADMIN, Role.RECEPTIONIST])
CanRegisterStaff = allow_roles(write=[Role.ADMIN])


class PatientCreateView(CreateAPIView):
    permission_classes = [CanRegisterPatients]
    serializer_class = PatientSerializer
    queryset = PatientProfile.objects.all()


class DoctorCreateView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = DoctorSerializer
    queryset = DoctorProfile.objects.all()


class NurseCreateView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = NurseSerializer
    queryset = NurseProfile.objects.all()


class LabTechCreateView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = LabTechSerializer
    queryset = LabTechProfile.objects.all()


class PharmacistCreateView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = PharmacistSerializer
    queryset = PharmacistProfile.objects.all()


class ReceptionistCreateView(CreateAPIView):
    permission_classes = [CanRegisterStaff]
    serializer_class = ReceptionistSerializer
    queryset = ReceptionistProfile.objects.all()
