'''
The email and SMS providers the platform can use. Each declares the
settings it needs; the operator dashboard builds its form from them.
To add a provider: subclass EmailProvider or SmsProvider and list it in PROVIDERS.
'''

import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from email.utils import parseaddr

from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.core.validators import validate_email


class ProviderError(Exception):
    '''The provider refused or could not be reached.'''


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    secret: bool = False
    required: bool = True
    default: str = ''
    help: str = ''


def _reason(error):
    '''The provider's own explanation, e.g. ZeptoMail's "Invalid API Token found".'''
    try:
        body = error.read().decode(errors='replace')
    except Exception:  # noqa: BLE001 (best effort for the error message)
        return ''
    try:
        data = json.loads(body)
    except ValueError:
        return body[:300]
    if not isinstance(data, dict):
        return body[:300]
    message = data.get('message')  # Termii: {"message": "..."}
    error_info = data.get('error')  # ZeptoMail: {"error": {"message": "...", "details": [{"message": "..."}]}}
    if isinstance(error_info, dict):
        details = [item.get('message') for item in error_info.get('details') or [] if isinstance(item, dict)]
        message = '; '.join(filter(None, details)) or error_info.get('message') or message
    return (message or body)[:300]


def post_json(url, payload, headers):
    request = urllib.request.Request(  # noqa: S310 (provider https URL, validated on save)
        url, data=json.dumps(payload).encode(), method='POST',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json', **headers},
    )  # fmt: skip
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (providers can be slow)
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raise ProviderError(f'Refused ({exc.code}): {_reason(exc)}') from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ProviderError(f'Could not reach the provider: {exc}') from exc


class Provider:
    channel = ''
    name = ''
    label = ''
    fields = ()
    # Console providers only print: never allowed as the active provider in production
    delivers = True

    def __init__(self, settings=None, secrets=None):
        values = {**(settings or {}), **(secrets or {})}
        self.values = {field.name: values.get(field.name, field.default) for field in self.fields}

    @classmethod
    def describe(cls):
        return {
            'channel': cls.channel, 'name': cls.name, 'label': cls.label, 'delivers': cls.delivers,
            'fields': [field.__dict__ for field in cls.fields],
        }  # fmt: skip

    @classmethod
    def validate(cls, values):
        '''Field errors for a complete set of values ({} when valid).'''
        return {
            field.name: 'This field is required.'
            for field in cls.fields
            if field.required and not str(values.get(field.name) or '').strip()
        }


# ---- Email ----


class EmailProvider(Provider):
    channel = 'email'

    def send_messages(self, messages):
        raise NotImplementedError

    def sender(self, message):
        '''(name, address) to send from: the provider's own from address, else the message's.'''
        name, address = parseaddr(self.values.get('from_email') or message.from_email)
        return name, address


class ConsoleEmail(EmailProvider):
    name, label, delivers = 'console', 'Console (development: prints emails)', False

    def send_messages(self, messages):
        return get_connection('django.core.mail.backends.console.EmailBackend').send_messages(messages)


def _check_from(values, errors):
    if values.get('from_email'):
        try:
            validate_email(parseaddr(values['from_email'])[1])
        except ValidationError:
            errors['from_email'] = 'Use an address like "St Luke\'s <no-reply@yourdomain.com>".'


class ZeptoMail(EmailProvider):
    name, label = 'zeptomail', 'ZeptoMail (Zoho)'
    fields = (
        Field('api_token', 'Send Mail token', secret=True,
              help='Mail Agents → your agent → SMTP/API → Send Mail Token'),
        Field('api_host', 'API host', default='api.zeptomail.com',
              help='Matches your account region: api.zeptomail.com, api.zeptomail.eu, api.zeptomail.in…'),
        Field('from_email', 'Send from', help='On your verified domain, e.g. HMS <no-reply@yourdomain.com>'),
    )  # fmt: skip

    @classmethod
    def validate(cls, values):
        errors = super().validate(values)
        if values.get('api_host') and not re.fullmatch(r'api\.zeptomail\.[a-z.]{2,10}', values['api_host']):
            errors['api_host'] = 'Use your region\'s API host, e.g. api.zeptomail.com.'
        _check_from(values, errors)
        return errors

    def send_messages(self, messages):
        token = re.sub(r'^Zoho-enczapikey\s+', '', self.values['api_token'].strip())  # pasted with or without prefix
        sent = 0
        for message in messages:
            name, address = self.sender(message)
            payload = {
                'from': {'address': address, **({'name': name} if name else {})},
                'to': [{'email_address': {'address': to}} for to in message.to],
                'subject': message.subject,
                'textbody': message.body,
            }
            if message.cc:
                payload['cc'] = [{'email_address': {'address': cc}} for cc in message.cc]
            if message.bcc:
                payload['bcc'] = [{'email_address': {'address': bcc}} for bcc in message.bcc]
            if message.reply_to:
                payload['reply_to'] = [{'address': parseaddr(reply)[1]} for reply in message.reply_to]
            html = next(
                (content for content, kind in getattr(message, 'alternatives', []) if kind == 'text/html'), None
            )
            if html:
                payload['htmlbody'] = html
            post_json(
                f'https://{self.values["api_host"]}/v1.1/email', payload, {'Authorization': f'Zoho-enczapikey {token}'}
            )
            sent += 1
        return sent


class SmtpEmail(EmailProvider):
    name, label = 'smtp', 'SMTP (any provider)'
    fields = (
        Field('host', 'SMTP server', help='e.g. smtp.zeptomail.com'),
        Field('port', 'Port', default='587'),
        Field('username', 'Username'),
        Field('password', 'Password', secret=True),
        Field('from_email', 'Send from', required=False, help='Optional; defaults to DEFAULT_FROM_EMAIL'),
    )

    @classmethod
    def validate(cls, values):
        errors = super().validate(values)
        if values.get('port') and not str(values['port']).isdigit():
            errors['port'] = 'A number, usually 587.'
        _check_from(values, errors)
        return errors

    def send_messages(self, messages):
        if self.values.get('from_email'):
            for message in messages:
                message.from_email = self.values['from_email']
        connection = get_connection(
            'django.core.mail.backends.smtp.EmailBackend',
            host=self.values['host'], port=int(self.values['port']), username=self.values['username'],
            password=self.values['password'], use_tls=True, timeout=10,
        )  # fmt: skip
        try:
            return connection.send_messages(messages)
        except Exception as exc:
            raise ProviderError(f'SMTP server refused: {exc}') from exc


# ---- SMS ----


class SmsProvider(Provider):
    channel = 'sms'

    def send(self, *, to, body, sender=''):
        '''Send one SMS to +<country><number>; returns the provider's message id.'''
        raise NotImplementedError


class ConsoleSms(SmsProvider):
    name, label, delivers = 'console', 'Console (development: prints messages)', False

    def send(self, *, to, body, sender=''):
        sys.stdout.write(f'\n--- SMS to {to} from {sender} ---\n{body}\n---\n')
        return f'console-{uuid.uuid4().hex[:12]}'


class Termii(SmsProvider):
    name, label = 'termii', 'Termii'
    fields = (
        Field('api_key', 'API key', secret=True, help='Termii dashboard → API settings'),
        Field('base_url', 'Base URL', default='https://api.ng.termii.com',
              help="Your account's base URL, shown in the Termii dashboard"),
        Field('sender_id', 'Sender ID', help='Approved by Termii, e.g. STLUKES. Hospitals may set their own'),
        Field('channel', 'Route', default='dnd',
              help='"dnd" reaches numbers on Do-Not-Disturb (ask Termii to activate it); "generic" otherwise'),
    )  # fmt: skip

    @classmethod
    def validate(cls, values):
        errors = super().validate(values)
        if values.get('base_url') and not re.fullmatch(r'https://[a-z0-9.-]+(:\d+)?/?', values['base_url']):
            errors['base_url'] = 'An https:// address, e.g. https://api.ng.termii.com'
        if values.get('sender_id') and not re.fullmatch(r'[A-Za-z0-9 ]{3,11}', values['sender_id']):
            errors['sender_id'] = '3-11 letters or digits.'
        if values.get('channel') not in (None, '', 'dnd', 'generic'):
            errors['channel'] = 'dnd or generic.'
        return errors

    def send(self, *, to, body, sender=''):
        result = post_json(
            f'{self.values["base_url"].rstrip("/")}/api/sms/send',
            {
                'api_key': self.values['api_key'],
                'to': to.lstrip('+'),
                'from': sender or self.values['sender_id'],
                'sms': body,
                'type': 'plain',
                'channel': self.values['channel'] or 'dnd',
            },  # fmt: skip
            {},
        )
        if not result.get('message_id'):
            raise ProviderError(result.get('message') or 'Termii did not accept the message.')
        return str(result['message_id'])


PROVIDERS = {
    (provider.channel, provider.name): provider for provider in (ConsoleEmail, ZeptoMail, SmtpEmail, ConsoleSms, Termii)
}
