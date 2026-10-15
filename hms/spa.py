'''
Serve the web app (frontend/dist) from the hospital's own address, next to its
API: same origin, so no CORS and a first-party session cookie. Assets
(/assets/*, /favicon.svg) are served by WhiteNoise (WHITENOISE_ROOT); every
other non-API path returns index.html and the app's router takes over.
'''

import json
from functools import lru_cache

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.urls import NoReverseMatch, reverse


@lru_cache(maxsize=1)
def _index_html():
    index = settings.FRONTEND_DIST / 'index.html'
    if not index.is_file():
        return None
    html = index.read_text(encoding='utf-8')
    # Runtime config, so one built frontend works on any domain
    config = json.dumps(
        {
            'tenantBaseDomain': settings.TENANT_BASE_DOMAIN,
            'apiUrl': '',
            'productName': settings.PRODUCT_NAME,
            'sentryDsn': settings.SENTRY_FRONTEND_DSN,
            'environment': settings.SENTRY_ENVIRONMENT,
        }
    ).replace('</', '<\\/')
    return html.replace('</head>', f'<script>window.__HMS_CONFIG__ = {config}</script></head>', 1)


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
    return response
