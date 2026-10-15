'''
URLs for the platform site (public schema), e.g. hms.app. Hospital sites
(stlukes.hms.app) use hms.urls. /api/health/ is answered by middleware on both.
'''

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from hms import spa
from legal.views import LegalDocumentView
from subscriptions.views import paystack_webhook

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # Platform operators sign in here (tokens are only valid on the platform site)
    path('api/v1/auth/', include('authentication.urls')),
    path('api/v1/platform/providers/', include('providers.urls')),
    path('api/v1/platform/', include('tenants.urls')),
    path('api/v1/platform/billing/paystack/webhook/', paystack_webhook, name='paystack-webhook'),
    # Self-serve signup (public, rate limited)
    path('api/v1/signup/', include('signup.urls')),
    path('api/v1/legal/<str:kind>/', LegalDocumentView.as_view(), name='legal-document'),
    # The web app: landing page and signup (everything that isn't the API)
    re_path(r'^(?!api/|static/)(?P<path>.*)$', spa.app, name='platform-app'),
]

handler404 = 'helpers.api.not_found'
handler500 = 'helpers.api.server_error'
