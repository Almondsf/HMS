from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    '''Read-only: the audit trail can be searched but never edited.'''

    list_display = [
        'occurred_at',
        'category',
        'action',
        'actor_email',
        'resource_type',
        'resource_id',
        'patient_id',
        'ip_address',
    ]
    list_filter = ['category', 'action', 'resource_type']
    search_fields = ['actor_email', 'resource_id', 'request_id']
    date_hierarchy = 'occurred_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
