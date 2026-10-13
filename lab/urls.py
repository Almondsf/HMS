from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LabTestViewSet, TestOrderViewSet, TestResultViewSet

router = DefaultRouter()
router.register(r'tests', LabTestViewSet, basename='tests')
router.register(r'test-orders', TestOrderViewSet, basename='test-orders')
router.register(r'test-results', TestResultViewSet, basename='test-results')

urlpatterns = [
    path('', include(router.urls)),
]
