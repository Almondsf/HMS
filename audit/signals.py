'''
Automatic change tracking for registered models.

Each instance remembers its field values when loaded (post_init, no extra
query), so saves can be diffed. Covers the API, admin and shell alike.
Bulk queryset.update()/bulk_create() bypass signals; code using them must
record explicitly (see pharmacy.services.dispense).
'''

from django.db.models.signals import post_delete, post_init, post_save
from django.dispatch import receiver

from .recorder import Category, record, to_json
from .registry import REDACTED_FIELDS, config_for

_SNAPSHOT = '_audit_snapshot'


def _snapshot(instance, config):
    # Only fields already loaded: touching deferred fields would trigger queries
    loaded = instance.__dict__
    return {
        f.attname: loaded[f.attname]
        for f in instance._meta.concrete_fields
        if f.attname in loaded and f.name not in config.exclude
    }


def _redact(changes):
    return {name: ['***', '***'] if name in REDACTED_FIELDS else values for name, values in changes.items()}


@receiver(post_init)
def remember_initial_values(sender, instance, **kwargs):
    config = config_for(sender)
    if config:
        # Note: _state.adding is still True here even for rows loaded from the
        # database (from_db sets it afterwards), so always snapshot; creates
        # ignore the snapshot anyway.
        setattr(instance, _SNAPSHOT, _snapshot(instance, config))


@receiver(post_save)
def record_save(sender, instance, created, raw=False, **kwargs):
    config = config_for(sender)
    if not config or raw:  # raw: loading fixtures
        return

    before = getattr(instance, _SNAPSHOT, {})
    after = to_json(_snapshot(instance, config))
    before = to_json(before)

    if created:
        changes = {name: [None, value] for name, value in after.items() if value not in (None, '')}
    else:
        changes = {name: [before.get(name), value] for name, value in after.items() if before.get(name) != value}
        if not changes:
            return

    record('create' if created else 'update', Category.DATA_CHANGE, resource=instance, changes=_redact(changes))
    setattr(instance, _SNAPSHOT, _snapshot(instance, config))


@receiver(post_delete)
def record_delete(sender, instance, **kwargs):
    config = config_for(sender)
    if config:
        snapshot = to_json(_snapshot(instance, config))
        changes = {name: [value, None] for name, value in snapshot.items()}
        record('delete', Category.DATA_CHANGE, resource=instance, changes=_redact(changes))
