from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuditEventViewSet

router = DefaultRouter()
router.register(r'events', AuditEventViewSet, basename='audit-events')

urlpatterns = [
    path('', include(router.urls)),
]
