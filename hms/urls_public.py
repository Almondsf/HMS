'''
URLs for the platform site (public schema), e.g. hms.app. Hospital sites
(stlukes.hms.app) use hms.urls. /api/health/ is answered by middleware on both.
'''

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # Platform operators sign in here (tokens are only valid on the platform site)
    path('api/auth/', include('authentication.urls')),
    path('api/platform/', include('tenants.urls')),
]
