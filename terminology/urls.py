from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import Icd10CodeViewSet

router = DefaultRouter()
router.register(r'icd10', Icd10CodeViewSet, basename='icd10')

urlpatterns = [
    path('', include(router.urls)),
]
