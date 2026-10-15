from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SmsMessageViewSet

router = DefaultRouter()
router.register(r'sms-messages', SmsMessageViewSet, basename='sms-messages')

urlpatterns = [path('', include(router.urls))]
