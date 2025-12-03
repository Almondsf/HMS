from django.contrib import admin
from .models import Visit, Consultation, Prescription, LabTestOrder

# --- 1. Registering models simply (quickest method) ---

admin.site.register(Visit)
admin.site.register(Consultation)
admin.site.register(Prescription)
admin.site.register(LabTestOrder)