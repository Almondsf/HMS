from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import HospitalViewSet, PlatformOverviewView, PlatformSignupViewSet

router = DefaultRouter()
router.register(r'hospitals', HospitalViewSet, basename='hospitals')
router.register(r'signups', PlatformSignupViewSet, basename='platform-signups')

urlpatterns = [
    path('overview/', PlatformOverviewView.as_view(), name='platform-overview'),
    path('', include(router.urls)),
]
