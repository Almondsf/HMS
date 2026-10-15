'''
Choosing, configuring, testing and switching the active email and SMS
providers. Sending code just asks for current(channel).

Without an active provider in the database, the server settings are used:
EMAIL_BACKEND / EMAIL_HOST... for email, SMS_BACKEND / SMS_API_KEY... for SMS.
'''

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from audit.recorder import Category, record
from helpers.sms import normalize

from . import crypto
from .models import Channel, ProviderConfig
from .registry import PROVIDERS, ProviderError


def provider_class(channel, name):
    cls = PROVIDERS.get((channel, name))
    if cls is None:
        raise ValidationError({'provider': f'Unknown {channel} provider "{name}".'})
    return cls


def build(config):
    return provider_class(config.channel, config.provider)(config.settings, crypto.decrypt(config.encrypted_secrets))


def active(channel):
    config = ProviderConfig.objects.filter(channel=channel, is_active=True).first()
    return build(config) if config else None


def from_server_settings(channel):
    '''The fallback configured in environment variables (SMS only; email falls back to EMAIL_BACKEND).'''
    if channel == Channel.SMS:
        if settings.SMS_BACKEND == 'console':
            return PROVIDERS[('sms', 'console')]()
        if settings.SMS_BACKEND == 'termii' and settings.SMS_API_KEY:
            return PROVIDERS[('sms', 'termii')](
                {'base_url': settings.SMS_API_URL or 'https://api.ng.termii.com', 'sender_id': settings.SMS_SENDER_ID},
                {'api_key': settings.SMS_API_KEY},
            )
    return None


def current(channel):
    return active(channel) or from_server_settings(channel)


def status(channel):
    '''What is delivering this channel now: (label, source), source "dashboard" or "server settings".'''
    provider = active(channel)
    if provider:
        return provider.label, 'dashboard'
    if channel == Channel.EMAIL:
        backend = settings.FALLBACK_EMAIL_BACKEND.rsplit('.', 2)[-2]
        label = {'smtp': f'SMTP ({settings.EMAIL_HOST or "not set"})', 'console': 'Console (prints emails)'}
        return label.get(backend, backend), 'server settings'
    fallback = from_server_settings(channel)
    return (fallback.label if fallback else 'Off'), 'server settings'


# ---- Managing configs (platform operators) ----


def serialize(config):
    cls = provider_class(config.channel, config.provider)
    secrets = crypto.decrypt(config.encrypted_secrets)
    return {
        'channel': config.channel,
        'provider': config.provider,
        'label': cls.label,
        'settings': {field.name: config.settings.get(field.name, '') for field in cls.fields if not field.secret},
        'secrets': {field.name: crypto.mask(secrets.get(field.name)) for field in cls.fields if field.secret},
        'is_active': config.is_active,
        'last_test_ok': config.last_test_ok,
        'last_tested_at': config.last_tested_at,
        'last_test_error': config.last_test_error,
        'updated_at': config.updated_at,
    }


@transaction.atomic
def save_config(*, channel, provider, values, by):
    '''
    Save a provider's settings. Secret fields left blank keep their stored
    value. Any change means the provider must pass a test again before it
    can be switched on (an active one stays active: test it right away).
    '''
    cls = provider_class(channel, provider)
    config = ProviderConfig.objects.select_for_update().filter(channel=channel, provider=provider).first()
    config = config or ProviderConfig(channel=channel, provider=provider)
    stored_secrets = crypto.decrypt(config.encrypted_secrets)

    known = {field.name: field for field in cls.fields}
    unknown = set(values) - set(known)
    if unknown:
        raise ValidationError({name: 'Not a setting of this provider.' for name in unknown})
    new_settings = {
        name: str(values.get(name, config.settings.get(name, field.default)) or '').strip()
        for name, field in known.items()
        if not field.secret
    }
    new_secrets = {
        name: str(values.get(name) or '').strip() or stored_secrets.get(name, '')
        for name, field in known.items()
        if field.secret
    }
    errors = cls.validate({**new_settings, **new_secrets})
    if errors:
        raise ValidationError(errors)

    changed = config.pk is None or new_settings != config.settings or new_secrets != stored_secrets
    config.settings = new_settings
    config.encrypted_secrets = crypto.encrypt({name: value for name, value in new_secrets.items() if value})
    if changed:
        config.last_test_ok, config.last_test_error = None, ''
    config.save()
    record(
        'providers.configured', Category.SECURITY,
        metadata={'channel': channel, 'provider': provider, 'changed_secrets': sorted(
            name for name in new_secrets if new_secrets[name] != stored_secrets.get(name, '')
        ), 'by': by.email},
    )  # fmt: skip
    return config


def test_config(*, channel, provider, to, by):
    '''Send a test message through this provider and remember whether it worked.'''
    config = ProviderConfig.objects.filter(channel=channel, provider=provider).first()
    if config is None:
        raise ValidationError({'provider': 'Save this provider\'s settings first.'})
    instance = build(config)
    try:
        if channel == Channel.EMAIL:
            message = EmailMessage(
                f'{settings.PRODUCT_NAME}: test email from {instance.label}',
                f'If you can read this, {instance.label} delivers your email.',
                settings.DEFAULT_FROM_EMAIL,
                [to],
            )
            instance.send_messages([message])
        else:
            number = normalize(to)
            if not number:
                raise ValidationError({'to': 'Enter a mobile number, e.g. 0803 123 4567.'})
            instance.send(to=number, body=f'{settings.PRODUCT_NAME}: test message from {instance.label}.')
    except ProviderError as exc:
        config.last_test_ok, config.last_test_error = False, str(exc)[:300]
    else:
        config.last_test_ok, config.last_test_error = True, ''
    config.last_tested_at = timezone.now()
    config.save(update_fields=['last_test_ok', 'last_test_error', 'last_tested_at', 'updated_at'])
    record(
        'providers.tested', Category.SECURITY,
        metadata={'channel': channel, 'provider': provider, 'ok': config.last_test_ok, 'by': by.email},
    )  # fmt: skip
    return config


@transaction.atomic
def activate(*, channel, provider, by):
    '''Switch the channel to this provider now; None goes back to the server settings.'''
    if channel not in Channel.values:
        raise ValidationError({'channel': 'email or sms.'})
    current_configs = ProviderConfig.objects.select_for_update().filter(channel=channel)
    if provider is None:
        current_configs.update(is_active=False)
    else:
        cls = provider_class(channel, provider)
        config = current_configs.filter(provider=provider).first()
        if config is None:
            raise ValidationError({'provider': 'Save this provider\'s settings first.'})
        if not cls.delivers and not settings.DEBUG:
            raise ValidationError({'provider': 'The console provider only prints messages: not for production.'})
        if not config.last_test_ok:
            raise ValidationError({'provider': 'Send a successful test with the current settings first.'})
        current_configs.exclude(pk=config.pk).update(is_active=False)
        config.is_active = True
        config.save(update_fields=['is_active', 'updated_at'])
    record(
        'providers.activated', Category.SECURITY, metadata={'channel': channel, 'provider': provider, 'by': by.email}
    )
