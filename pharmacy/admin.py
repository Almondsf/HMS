from django.contrib import admin

from .models import DispensedItem, DispenseTransaction, Drug


@admin.register(Drug)
class DrugAdmin(admin.ModelAdmin):
    list_display = ['name', 'unit', 'quantity_in_stock', 'reorder_level']
    search_fields = ['name']


class DispensedItemInline(admin.TabularInline):
    model = DispensedItem
    extra = 0


@admin.register(DispenseTransaction)
class DispenseTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'pharmacist', 'dispensed_at']
    inlines = [DispensedItemInline]


admin.site.register(DispensedItem)
