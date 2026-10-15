from rest_framework import serializers, viewsets

from authentication.permissions import Role, allow_roles

from .models import SmsMessage


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
