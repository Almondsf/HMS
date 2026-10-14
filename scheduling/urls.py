from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppointmentViewSet

router = DefaultRouter()
router.register(r'appointments', AppointmentViewSet, basename='appointments')

urlpatterns = [
    path('', include(router.urls)),
]
