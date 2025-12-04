from django.contrib import admin
from .models import Drug, DispenseTransaction, DispensedItem

# Register your models here.

admin.site.register(Drug)
admin.site.register(DispenseTransaction)
admin.site.register(DispensedItem)
