from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet, SmsMessageViewSet

router = DefaultRouter()
router.register(r'sms-messages', SmsMessageViewSet, basename='sms-messages')
router.register(r'notifications', NotificationViewSet, basename='notifications')

urlpatterns = [path('', include(router.urls))]
