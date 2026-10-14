from django.contrib import admin
from django.db import connection
from django_tenants.utils import get_public_schema_name

from .models import Domain, Hospital


class PlatformOnlyAdmin(admin.ModelAdmin):
    '''
    Hospital records live in the shared schema, which is also readable from
    every hospital's schema. Only expose them on the platform (public) site.
    '''

    def has_module_permission(self, request):
        return connection.schema_name == get_public_schema_name() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return connection.schema_name == get_public_schema_name() and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return False  # use the create_hospital command / platform API, which also provisions the schema

    def has_change_permission(self, request, obj=None):
        return connection.schema_name == get_public_schema_name() and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 0


@admin.register(Hospital)
class HospitalAdmin(PlatformOnlyAdmin):
    list_display = ['name', 'schema_name', 'plan', 'is_active', 'created_at']
    list_filter = ['plan', 'is_active']
    search_fields = ['name', 'schema_name', 'domains__domain']
    readonly_fields = ['schema_name', 'created_at']
    inlines = [DomainInline]
