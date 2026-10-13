'''
Which models are audited, and how to find the patient a record belongs to.
Apps register their own models in AppConfig.ready(), e.g.:

    audit.registry.register(Visit, patient=lambda visit: visit.patient_id)
'''

from collections.abc import Callable
from dataclasses import dataclass, field

# Never written to the audit log in clear text
REDACTED_FIELDS = {'password'}
# Noise: changes on every save
IGNORED_FIELDS = {'updated_at', 'last_login'}


@dataclass(frozen=True)
class AuditConfig:
    patient: Callable | None = None
    exclude: frozenset = field(default_factory=frozenset)


_registry: dict[type, AuditConfig] = {}


def register(model, *, patient=None, exclude=()):
    _registry[model] = AuditConfig(patient=patient, exclude=frozenset(exclude) | IGNORED_FIELDS)


def config_for(model):
    return _registry.get(model)


def resource_type(obj_or_model):
    meta = obj_or_model._meta
    return f'{meta.app_label}.{meta.model_name}'


def patient_id_for(obj):
    '''PatientProfile id for an audited record, or None.'''
    config = config_for(type(obj))
    if not (config and config.patient):
        return None
    try:
        return config.patient(obj)
    except AttributeError:  # e.g. a relation not set yet
        return None
