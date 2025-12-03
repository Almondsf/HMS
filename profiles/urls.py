from django.urls import path
from profiles.views import patientView, doctorView, labTechView, pharmacistView, receptionistView

urlpatterns = [
    path('patients/', patientView.as_view(), name='create-patient'),
    path('doctors/', doctorView.as_view(), name='create-doctor'),
    path('labtechs/', labTechView.as_view(), name='create-labtech'),
    path('pharmacists/', pharmacistView.as_view(), name='create-pharmacist'),
    path('receptionists/', receptionistView.as_view(), name='create-receptionist'),
]