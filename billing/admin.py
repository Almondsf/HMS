from django.contrib import admin

from .models import Invoice, InvoiceLine, Payment, ServiceItem


@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'price', 'charge_on', 'is_active']
    list_filter = ['category', 'charge_on', 'is_active']
    search_fields = ['code', 'name']


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class LineInline(ReadOnlyInline):
    model = InvoiceLine


class PaymentInline(ReadOnlyInline):
    model = Payment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    '''Read-only: money moves only through the API, where the rules are enforced.'''

    list_display = ['number', 'patient', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['number', 'patient__mrn', 'patient__user__last_name']
    inlines = [LineInline, PaymentInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
