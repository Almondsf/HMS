'''Write audit events. The one entry point every app uses.'''

import json
import logging

from django.core.serializers.json import DjangoJSONEncoder

from . import context
from .models import AuditEvent
from .registry import patient_id_for, resource_type

Category = AuditEvent.Category

logger = logging.getLogger('hms.audit')


def to_json(value):
    '''Make values (dates, decimals, UUIDs...) safe for a JSONField.'''
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def record(action, category, *, resource=None, resource_type_name='', patient_id=None,
           changes=None, metadata=None, actor=None):
    '''
    Record an audit event. The actor, client IP, user agent and request id
    are taken from the current request unless given.
    '''
    request = context.current_request()
    actor = actor or context.current_user()

    if resource is not None:
        resource_type_name = resource_type(resource)
        if patient_id is None:
            patient_id = patient_id_for(resource)

    event = AuditEvent.objects.create(
        category=category,
        action=action,
        actor_id=getattr(actor, 'pk', None),
        actor_email=getattr(actor, 'email', ''),
        actor_role=getattr(actor, 'user_type', ''),
        resource_type=resource_type_name,
        resource_id=str(resource.pk) if resource is not None else '',
        patient_id=patient_id,
        changes=to_json(changes or {}),
        metadata=to_json(metadata or {}),
        ip_address=context.client_ip(request) if request else None,
        user_agent=request.headers.get('User-Agent', '')[:255] if request else '',
        request_id=context.current_request_id(),
    )

    logger.info(
        '%s %s', category, action,
        extra={
            'audit_event_id': event.pk,
            'actor_id': event.actor_id,
            'resource': f'{event.resource_type}#{event.resource_id}' if event.resource_type else None,
            'patient_id': event.patient_id,
        },
    )
    return event
