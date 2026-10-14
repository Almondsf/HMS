from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .directory_views import DepartmentViewSet, PatientViewSet, StaffViewSet

router = DefaultRouter()
router.register(r'patients', PatientViewSet, basename='patients')
router.register(r'staff', StaffViewSet, basename='staff')
router.register(r'departments', DepartmentViewSet, basename='departments')

urlpatterns = [
    path('', include(router.urls)),
]
