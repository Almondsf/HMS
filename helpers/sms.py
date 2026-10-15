'''
Sending SMS. Pick a provider with SMS_BACKEND:

  ''              off: nothing is sent (the default in production until configured)
  console         prints messages to the server console (the default in development)
  termii          Termii (https://termii.com): SMS_API_KEY, optionally SMS_API_URL
  africastalking  Africa's Talking: SMS_API_KEY and SMS_USERNAME ("sandbox" for testing)

Sender IDs (the name a patient sees) must be registered with the provider
before use. Standard library only, like the Paystack client.
'''

import json
import logging
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from django.conf import settings

logger = logging.getLogger('hms.sms')


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


def _post(url, *, data, headers):
    request = urllib.request.Request(url, data=data, method='POST', headers=headers)  # noqa: S310 (configured https URL)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode(errors='replace')[:300]
        except Exception:  # noqa: BLE001 (best effort for the error message)
            body = ''
        raise SmsError(f'Provider refused the message ({exc.code}): {body}') from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SmsError(f'Could not reach the SMS provider: {exc}') from exc


class ConsoleBackend:
    name = 'console'

    def send(self, *, to, body, sender):
        sys.stdout.write(f'\n--- SMS to {to} from {sender} ---\n{body}\n---\n')
        return f'console-{uuid.uuid4().hex[:12]}'


class TermiiBackend:
    name = 'termii'

    def send(self, *, to, body, sender):
        result = _post(
            f'{settings.SMS_API_URL or "https://api.ng.termii.com"}/api/sms/send',
            data=json.dumps(
                {
                    'api_key': settings.SMS_API_KEY,
                    'to': to.lstrip('+'),
                    'from': sender,
                    'sms': body,
                    'type': 'plain',
                    'channel': 'dnd',  # dnd: delivered to numbers on Do-Not-Disturb too
                }
            ).encode(),  # fmt: skip
            headers={'Content-Type': 'application/json'},
        )
        if not result.get('message_id'):
            raise SmsError(result.get('message') or 'Termii did not accept the message.')
        return str(result['message_id'])


class AfricasTalkingBackend:
    name = 'africastalking'

    def send(self, *, to, body, sender):
        sandbox = settings.SMS_USERNAME == 'sandbox'
        url = f'https://api.{"sandbox." if sandbox else ""}africastalking.com/version1/messaging'
        form = {'username': settings.SMS_USERNAME, 'to': to, 'message': body}
        if sender and not sandbox:
            form['from'] = sender
        result = _post(
            url,
            data=urllib.parse.urlencode(form).encode(),
            headers={'apiKey': settings.SMS_API_KEY, 'Accept': 'application/json'},
        )
        recipients = (result.get('SMSMessageData') or {}).get('Recipients') or []
        if not recipients or recipients[0].get('status') != 'Success':
            reason = recipients[0].get('status') if recipients else (result.get('SMSMessageData') or {}).get('Message')
            raise SmsError(f"Africa's Talking did not accept the message: {reason}")
        return recipients[0].get('messageId', '')


BACKENDS = {backend.name: backend for backend in (ConsoleBackend, TermiiBackend, AfricasTalkingBackend)}


def available():
    return settings.SMS_BACKEND in BACKENDS


def send(*, to, body, sender=''):
    '''Send one SMS; returns (provider name, provider's message id). Raises SmsError.'''
    if not available():
        raise SmsError('SMS is not set up (SMS_BACKEND).')
    backend = BACKENDS[settings.SMS_BACKEND]()
    return backend.name, backend.send(to=to, body=body, sender=sender or settings.SMS_SENDER_ID)
