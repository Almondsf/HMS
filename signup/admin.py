from django.contrib import admin

from tenants.admin import PlatformOnlyAdmin

from .models import Signup


@admin.register(Signup)
class SignupAdmin(PlatformOnlyAdmin):
    '''Read-only: see who signed up and whether their hospital was created.'''

    list_display = ['created_at', 'hospital_name', 'address', 'plan', 'email', 'status', 'hospital']
    list_filter = ['status', 'plan']
    search_fields = ['hospital_name', 'address', 'email']
    exclude = ['password_hash', 'token_hash']

    def has_change_permission(self, request, obj=None):
        return False
