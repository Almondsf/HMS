from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication

from tenants.views import HospitalExportView, HospitalSettingsView

from . import spa

# Docs are open in development; in production only staff signed in to the admin can view them
schema_view = get_schema_view(
    openapi.Info(
        title=f'{settings.PRODUCT_NAME} API',
        default_version='v1',
        description='Hospital management API',
    ),
    public=settings.API_DOCS_PUBLIC,
    authentication_classes=(SessionAuthentication,),
    permission_classes=(permissions.AllowAny if settings.API_DOCS_PUBLIC else permissions.IsAdminUser,),
)

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('api/v1/auth/', include('authentication.urls')),
    path('api/v1/hospital/', HospitalSettingsView.as_view(), name='hospital-settings'),
    path('api/v1/hospital/export/', HospitalExportView.as_view(), name='hospital-export'),
    path('api/v1/subscription/', include('subscriptions.urls')),
    path('api/v1/create-profile/', include('profiles.urls')),
    path('api/v1/', include('clinical.urls')),
    path('api/v1/', include('profiles.directory_urls')),
    path('api/v1/', include('scheduling.urls')),
    path('api/v1/', include('terminology.urls')),
    path('api/v1/', include('notifications.urls')),
    path('api/v1/pharmacy/', include('pharmacy.urls')),
    path('api/v1/lab/', include('lab.urls')),
    path('api/v1/billing/', include('billing.urls')),
    path('api/v1/insurance/', include('insurance.urls')),
    path('api/v1/reports/', include('reports.urls')),
    path('api/v1/audit/', include('audit.urls')),
    # API docs
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    re_path(r'^api/schema\.(?P<format>json|yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    # Everything else is the web app (client-side routes); unknown /api/ paths still 404 as JSON
    re_path(r'^(?!api/|static/)(?P<path>.*)$', spa.app, name='app'),
]

handler404 = 'helpers.api.not_found'
handler500 = 'helpers.api.server_error'
