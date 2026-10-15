from django.contrib import admin, messages
from django.utils import timezone

from tenants.admin import PlatformOnlyAdmin

from .models import LegalDocument


@admin.register(LegalDocument)
class LegalDocumentAdmin(PlatformOnlyAdmin):
    '''
    To change the terms or privacy policy: add a new version, then publish it.
    Published versions are locked, because signups record which one they accepted.
    '''

    list_display = ['kind', 'version', 'is_draft', 'published_at']
    list_filter = ['kind']
    actions = ['publish']

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request) and (obj is None or obj.published_at is None)

    @admin.action(description='Publish (becomes the version new signups accept)')
    def publish(self, request, queryset):
        published = queryset.filter(published_at__isnull=True).update(published_at=timezone.now())
        self.message_user(request, f'Published {published} document(s).', messages.SUCCESS)
