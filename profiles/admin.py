from django.contrib import admin

from .models import (
    CashierProfile,
    DoctorProfile,
    LabTechProfile,
    PatientProfile,
    PharmacistProfile,
    ReceptionistProfile,
)

USER_SEARCH = ['user__first_name', 'user__last_name', 'user__email']


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'blood_group', 'genotype', 'assigned_doctor']
    search_fields = USER_SEARCH
    list_select_related = ['user', 'assigned_doctor__user']


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'specialty', 'license_number']
    search_fields = [*USER_SEARCH, 'specialty']
    list_select_related = ['user']


@admin.register(LabTechProfile, PharmacistProfile, ReceptionistProfile, CashierProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    search_fields = USER_SEARCH
    list_select_related = ['user']
