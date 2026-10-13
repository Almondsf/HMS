from django.contrib import admin

from .models import Consultation, Prescription, Visit


class ConsultationInline(admin.StackedInline):
    model = Consultation
    extra = 0
    show_change_link = True


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 0
    autocomplete_fields = ['drug']


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'assigned_doctor', 'status', 'visit_date']
    list_filter = ['status', 'visit_date']
    search_fields = ['patient__user__first_name', 'patient__user__last_name', 'patient__user__email']
    list_select_related = ['patient__user', 'assigned_doctor__user']
    inlines = [ConsultationInline]


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ['id', 'visit', 'follow_up_date', 'created_at']
    list_select_related = ['visit__patient__user']
    inlines = [PrescriptionInline]


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'medication_name', 'drug', 'dosage', 'quantity', 'consultation']
    search_fields = ['medication_name', 'drug__name']
    autocomplete_fields = ['drug']
