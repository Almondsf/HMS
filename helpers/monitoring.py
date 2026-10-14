'''
Error monitoring (Sentry), set up so that no patient data leaves the server.

Errors arrive with the stack trace, the hospital, the request id (to find the
matching logs and audit events) and the signed-in user's internal id and
role. Never sent: request bodies, query strings (a search like
?search=ada obi is patient data), cookies, auth headers, local variables
(they may hold patient records) or names and emails.
'''

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

SAFE_HEADERS = {'User-Agent', 'X-Request-Id', 'Host', 'Content-Type', 'Accept'}


def _scrub(event, hint):
    request = event.get('request')
    if request:
        request.pop('data', None)
        request.pop('cookies', None)
        request['query_string'] = ''
        if isinstance(request.get('url'), str):
            request['url'] = request['url'].split('?', 1)[0]
        request['headers'] = {k: v for k, v in (request.get('headers') or {}).items() if k.title() in SAFE_HEADERS}

    # Breadcrumbs can carry URLs with search terms
    for crumb in (event.get('breadcrumbs') or {}).get('values', []):
        data = crumb.get('data') or {}
        if isinstance(data.get('url'), str):
            data['url'] = data['url'].split('?', 1)[0]

    tags = event.setdefault('tags', {})
    try:
        from django.db import connection

        from audit.context import current_request_id, current_user

        tags['hospital'] = getattr(connection, 'schema_name', '')
        tags['request_id'] = current_request_id()
        user = current_user()
        if user is not None:
            event['user'] = {'id': str(user.pk)}  # internal id only, no name or email
            tags['role'] = user.user_type
    except Exception:  # noqa: S110  never break error reporting; logging here could loop into Sentry
        pass
    return event


def init_sentry(*, dsn, environment, release='', traces_sample_rate=0.0):
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release or None,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        max_request_body_size='never',
        include_local_variables=False,
        traces_sample_rate=traces_sample_rate,
        before_send=_scrub,
    )
