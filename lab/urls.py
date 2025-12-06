from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TestsViewSet, TestOrderViewSet, TestResultViewSet

router = DefaultRouter()
router.register(r'tests', TestsViewSet, basename='tests')
router.register(r'test-orders', TestOrderViewSet, basename='test-orders')
router.register(r'test-results', TestResultViewSet, basename='test-results')
urlpatterns = [
    path('', include(router.urls)),
]