from django.utils.dateparse import parse_datetime
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from authentication.permissions import Role, allow_roles

from .models import AuditEvent
from .serializers import AuditEventSerializer

EXACT_FILTERS = ['category', 'action', 'actor_id', 'resource_type', 'resource_id', 'request_id']


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    Audit trail for hospital admins. Filters: category, action, actor_id,
    resource_type, resource_id, request_id, patient (also matches list views
    that showed the patient), since / until (ISO 8601).
    '''
    serializer_class = AuditEventSerializer
    permission_classes = [allow_roles(read=[Role.ADMIN])]

    def get_queryset(self):
        params = self.request.query_params
        events = AuditEvent.objects.filter(
            **{name: params[name] for name in EXACT_FILTERS if name in params}
        )

        if 'patient' in params:
            try:
                patient = int(params['patient'])
            except ValueError:
                raise ValidationError({'patient': 'Must be a patient id.'})
            events = events.filter(patient_id=patient) | events.filter(metadata__patient_ids__contains=[patient])

        for name, lookup in (('since', 'occurred_at__gte'), ('until', 'occurred_at__lte')):
            if name in params:
                moment = parse_datetime(params[name])
                if moment is None:
                    raise ValidationError({name: 'Use ISO 8601, e.g. 2026-01-31T09:00:00Z.'})
                events = events.filter(**{lookup: moment})
        return events
