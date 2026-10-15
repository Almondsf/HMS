from django.contrib import admin

from tenants.admin import PlatformOnlyAdmin

from .models import ProviderConfig


@admin.register(ProviderConfig)
class ProviderConfigAdmin(PlatformOnlyAdmin):
    '''Read-only here: configure providers in the operator dashboard (keys are encrypted).'''

    list_display = ['channel', 'provider', 'is_active', 'last_test_ok', 'last_tested_at']
    exclude = ['encrypted_secrets']

    def has_change_permission(self, request, obj=None):
        return False
