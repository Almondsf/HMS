from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import Role, allow_roles

from .models import Notification, SmsMessage


class SmsMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsMessage
        fields = [
            'id', 'created_at', 'kind', 'patient', 'appointment', 'appointment_starts_at', 'to', 'body', 'status',
            'error', 'sent_at',
        ]  # fmt: skip


class SmsMessageViewSet(viewsets.ReadOnlyModelViewSet):
    '''SMS sent to patients (or not sent, with the reason). Filter with ?patient= or ?appointment=.'''

    queryset = SmsMessage.objects.all()
    serializer_class = SmsMessageSerializer
    permission_classes = [allow_roles(read=[Role.ADMIN, Role.RECEPTIONIST], write=[])]
    filterset_fields = ['patient', 'appointment', 'status', 'kind']


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'kind', 'level', 'title', 'body', 'link', 'created_at', 'read_at', 'is_read']

    def get_is_read(self, notification):
        return notification.read_at is not None


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    '''The signed-in person's notifications, newest first. ?unread=true for unread only.'''

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        mine = Notification.objects.filter(recipient=self.request.user)
        if self.request.query_params.get('unread') in ('true', '1'):
            mine = mine.filter(read_at__isnull=True)
        return mine

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        return Response({'count': Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()})

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        updated = Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response({'marked_read': updated})
