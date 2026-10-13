'''
Domain events: things that happened in the hospital ("lab.result_completed",
"pharmacy.stock_low") that other parts of the system can react to, e.g. SMS
notifications or billing, without the producing code knowing about them.

    from audit import events

    @events.subscribe('lab.result_completed')
    def notify_doctor(event):  # event: DomainEvent
        ...

    events.publish('lab.result_completed', resource=result, test=result.test.name)

Events are delivered only after the surrounding transaction commits, so a
rolled-back action never triggers side effects. Every event is also written
to the audit log.
'''

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction

from .recorder import Category, record

logger = logging.getLogger('hms.events')

_subscribers = defaultdict(list)


@dataclass(frozen=True)
class DomainEvent:
    name: str
    resource: object = None
    payload: dict = field(default_factory=dict)


def subscribe(name):
    def decorator(handler):
        _subscribers[name].append(handler)
        return handler
    return decorator


def publish(name, *, resource=None, patient_id=None, **payload):
    '''patient_id is only needed when it can't be derived from the resource.'''
    if patient_id is not None:
        payload['patient_id'] = patient_id
    event = DomainEvent(name=name, resource=resource, payload=payload)
    record(name, Category.DOMAIN, resource=resource, patient_id=patient_id, metadata=payload)
    transaction.on_commit(lambda: _deliver(event))


def _deliver(event):
    for handler in _subscribers[event.name]:
        try:
            handler(event)
        except Exception:
            # One failing subscriber must not break the request or the others
            logger.exception('Handler %s failed for event %s', getattr(handler, '__name__', handler), event.name)
