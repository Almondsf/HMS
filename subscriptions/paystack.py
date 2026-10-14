'''
Minimal Paystack API client (standard library only).
Docs: https://paystack.com/docs/api/ . Amounts are in kobo.
'''

import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

API = 'https://api.paystack.co'


class PaystackError(Exception):
    pass


def _request(method, path, payload=None):
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError('Online payments are not configured (PAYSTACK_SECRET_KEY).')
    request = urllib.request.Request(  # noqa: S310 (fixed https URL)
        f'{API}{path}',
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read()).get('message', str(exc))
        except ValueError:
            message = str(exc)
        raise PaystackError(message) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PaystackError(f'Could not reach Paystack: {exc}') from exc
    if not body.get('status'):
        raise PaystackError(body.get('message', 'Paystack rejected the request.'))
    return body['data']


def initialize_transaction(*, email, amount_kobo, reference, callback_url, metadata, plan_code=''):
    '''Start a checkout; returns {authorization_url, access_code, reference}. With a plan code, it renews.'''
    payload = {
        'email': email,
        'amount': amount_kobo,
        'reference': reference,
        'callback_url': callback_url,
        'metadata': metadata,
    }
    if plan_code:
        payload['plan'] = plan_code
    return _request('POST', '/transaction/initialize', payload)


def verify_transaction(reference):
    return _request('GET', f'/transaction/verify/{urllib.parse.quote(reference)}')


def create_plan(*, name, interval, amount_kobo, currency='NGN'):
    return _request(
        'POST',
        '/plan',
        {
            'name': name,
            'interval': 'annually' if interval == 'yearly' else 'monthly',
            'amount': amount_kobo,
            'currency': currency,
        },
    )


def disable_subscription(*, code, email_token):
    return _request('POST', '/subscription/disable', {'code': code, 'token': email_token})


def valid_signature(raw_body, signature):
    '''Webhooks are signed with HMAC-SHA512 of the raw body using the secret key.'''
    if not settings.PAYSTACK_SECRET_KEY or not signature:
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
