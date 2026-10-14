from django.urls import path

from profiles.views import (
    CashierCreateView,
    DoctorCreateView,
    LabTechCreateView,
    NurseCreateView,
    PatientCreateView,
    PharmacistCreateView,
    ReceptionistCreateView,
)

urlpatterns = [
    path('patients/', PatientCreateView.as_view(), name='create-patient'),
    path('doctors/', DoctorCreateView.as_view(), name='create-doctor'),
    path('nurses/', NurseCreateView.as_view(), name='create-nurse'),
    path('labtechs/', LabTechCreateView.as_view(), name='create-labtech'),
    path('pharmacists/', PharmacistCreateView.as_view(), name='create-pharmacist'),
    path('receptionists/', ReceptionistCreateView.as_view(), name='create-receptionist'),
    path('cashiers/', CashierCreateView.as_view(), name='create-cashier'),
]
