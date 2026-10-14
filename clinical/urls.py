from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConsultationViewSet,
    DiagnosisViewSet,
    PrescriptionViewSet,
    QueueView,
    VisitViewSet,
    VitalSignsViewSet,
)

router = DefaultRouter()
router.register(r'visits', VisitViewSet, basename='visits')
router.register(r'consultations', ConsultationViewSet, basename='consultations')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescriptions')
router.register(r'vitals', VitalSignsViewSet, basename='vitals')
router.register(r'diagnoses', DiagnosisViewSet, basename='diagnoses')

urlpatterns = [
    path('queue/', QueueView.as_view(), name='queue'),
    path('', include(router.urls)),
]
