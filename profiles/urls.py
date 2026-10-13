from django.urls import path

from profiles.views import (
    DoctorCreateView,
    LabTechCreateView,
    PatientCreateView,
    PharmacistCreateView,
    ReceptionistCreateView,
)

urlpatterns = [
    path('patients/', PatientCreateView.as_view(), name='create-patient'),
    path('doctors/', DoctorCreateView.as_view(), name='create-doctor'),
    path('labtechs/', LabTechCreateView.as_view(), name='create-labtech'),
    path('pharmacists/', PharmacistCreateView.as_view(), name='create-pharmacist'),
    path('receptionists/', ReceptionistCreateView.as_view(), name='create-receptionist'),
]
