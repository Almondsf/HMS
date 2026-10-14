from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['starts_at', 'patient', 'doctor', 'status']
    list_filter = ['status', 'doctor']
    date_hierarchy = 'starts_at'
    list_select_related = ['patient__user', 'doctor__user']
