'''
Serve the web app (frontend/dist) from the hospital's own address, next to its
API: same origin, so no CORS and a first-party session cookie. Assets
(/assets/*, /favicon.svg) are served by WhiteNoise (WHITENOISE_ROOT); every
other non-API path returns index.html and the app's router takes over.
'''

import base64
import hashlib
import json
from functools import lru_cache
from urllib.parse import urlsplit

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.urls import NoReverseMatch, reverse


def _config_script():
    '''Runtime config, so one built frontend works on any domain.'''
    config = json.dumps(
        {
            'tenantBaseDomain': settings.TENANT_BASE_DOMAIN,
            'apiUrl': '',
            'productName': settings.PRODUCT_NAME,
            'sentryDsn': settings.SENTRY_FRONTEND_DSN,
            'environment': settings.SENTRY_ENVIRONMENT,
        }
    ).replace('</', '<\\/')
    return f'window.__HMS_CONFIG__ = {config}'


@lru_cache(maxsize=1)
def _index_html():
    index = settings.FRONTEND_DIST / 'index.html'
    if not index.is_file():
        return None
    html = index.read_text(encoding='utf-8')
    return html.replace('</head>', f'<script>{_config_script()}</script></head>', 1)


def content_security_policy():
    '''
    What the browser may load and run on our pages: scripts only from our own
    origin plus the one inline config script (allowed by its hash), so an
    injected <script> can't run; error reports may go to Sentry only.
    '''
    digest = base64.b64encode(hashlib.sha256(_config_script().encode()).digest()).decode()
    connect = ["'self'"]
    if settings.SENTRY_FRONTEND_DSN:
        dsn = urlsplit(settings.SENTRY_FRONTEND_DSN)
        connect.append(f'{dsn.scheme}://{dsn.hostname}')
    return '; '.join([
        "default-src 'self'",
        f"script-src 'self' 'sha256-{digest}'",
        "style-src 'self' 'unsafe-inline'",  # React style attributes, e.g. chart bar widths
        "img-src 'self' data:",
        "font-src 'self' data:",
        f"connect-src {' '.join(connect)}",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])  # fmt: skip


def app(request, path=''):
    html = _index_html()
    if html is None:
        # API-only deployment (frontend not built): send people to the API docs, if this site has them
        try:
            return HttpResponseRedirect(reverse('schema-swagger-ui'))
        except NoReverseMatch:
            raise Http404 from None
    response = HttpResponse(html)
    response['Cache-Control'] = 'no-cache'  # always pick up a new deploy; assets are fingerprinted
    response['Content-Security-Policy'] = content_security_policy()
    return response
