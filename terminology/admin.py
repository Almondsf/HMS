from django.contrib import admin
from django.db import connection
from django_tenants.utils import get_public_schema_name

from tenants.admin import PlatformOnlyAdmin

from .models import Icd10Code


@admin.register(Icd10Code)
class Icd10CodeAdmin(PlatformOnlyAdmin):
    '''Shared by every hospital, so only editable on the platform site.'''

    list_display = ['code', 'title', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'title']

    def has_add_permission(self, request):
        return connection.schema_name == get_public_schema_name() and request.user.is_superuser
