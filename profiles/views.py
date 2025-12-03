# profile/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from profiles.serializers import PatientSerializer, DoctorSerializer, LabTechSerializer, PharmacistSerializer
from rest_framework.generics import CreateAPIView
from .models import PatientProfile, DoctorProfile, LabTechProfile, PharmacistProfile


class patientView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = PatientSerializer
    queryset = PatientProfile.objects.all()

class doctorView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = DoctorSerializer
    queryset = DoctorProfile.objects.all()

class labTechView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = LabTechSerializer
    queryset = LabTechProfile.objects.all()

class pharmacistView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = PharmacistSerializer
    queryset = PharmacistProfile.objects.all()

class receptionistView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = PharmacistSerializer
    queryset = PharmacistProfile.objects.all()