from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            'id', 'occurred_at', 'category', 'action', 'actor_id', 'actor_email', 'actor_role',
            'resource_type', 'resource_id', 'patient_id', 'changes', 'metadata',
            'ip_address', 'user_agent', 'request_id',
        ]
