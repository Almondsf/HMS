from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ClaimViewSet, CoverageViewSet, InsuranceProviderViewSet

router = DefaultRouter()
router.register(r'providers', InsuranceProviderViewSet, basename='insurance-providers')
router.register(r'coverages', CoverageViewSet, basename='coverages')
router.register(r'claims', ClaimViewSet, basename='claims')

urlpatterns = [
    path('', include(router.urls)),
]
