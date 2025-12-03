from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VisitViewSet, ConsultationViewSet

router = DefaultRouter()
router.register(r'visits', VisitViewSet, basename='visits')
router.register(r'consultations', ConsultationViewSet, basename='consultations')

urlpatterns = [
    path('', include(router.urls)),
]