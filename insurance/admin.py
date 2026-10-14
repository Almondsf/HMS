from django.contrib import admin

from .models import Claim, Coverage, InsuranceProvider


@admin.register(InsuranceProvider)
class InsuranceProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'kind', 'default_coverage_percent', 'requires_authorization', 'is_active']
    list_filter = ['kind', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Coverage)
class CoverageAdmin(admin.ModelAdmin):
    list_display = ['patient', 'provider', 'member_number', 'valid_from', 'valid_to', 'is_active']
    list_filter = ['provider', 'is_active']
    search_fields = ['member_number', 'patient__mrn', 'patient__user__last_name']


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    '''Read-only: claims move through the API, where the money rules are enforced.'''

    list_display = ['number', 'invoice', 'status', 'claimed_amount', 'approved_amount', 'paid_amount']
    list_filter = ['status']
    search_fields = ['number', 'invoice__number']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
