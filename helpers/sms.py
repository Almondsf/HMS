'''
Sending SMS through the active SMS provider (see providers/): Termii, or the
console in development. A platform operator picks and switches it in the
operator dashboard; without one, the SMS_BACKEND server settings apply.
'''

import re

from django.conf import settings


class SmsError(Exception):
    pass


def normalize(number):
    '''A phone number as +<country><number>, or None if it can't be a mobile number. "0803..." -> "+234803...".'''
    digits = re.sub(r'[\s\-().]', '', number or '')
    if digits.startswith('+'):
        digits = digits[1:]
    elif digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = settings.SMS_DEFAULT_COUNTRY_CODE + digits[1:]
    if not re.fullmatch(r'[1-9]\d{9,14}', digits):
        return None
    return f'+{digits}'


def _provider():
    from providers import services  # providers imports this module

    return services.current('sms')


def available():
    return _provider() is not None


def send(*, to, body, sender=''):
    '''Send one SMS; returns (provider name, provider's message id). Raises SmsError.'''
    from providers.registry import ProviderError

    provider = _provider()
    if provider is None:
        raise SmsError('SMS is not set up: choose a provider in the operator dashboard.')
    try:
        return provider.name, provider.send(to=to, body=body, sender=sender)
    except ProviderError as exc:
        raise SmsError(str(exc)) from exc
