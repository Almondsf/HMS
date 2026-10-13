from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profiles'

    def ready(self):
        from audit import registry

        from .models import DoctorProfile, LabTechProfile, PatientProfile, PharmacistProfile, ReceptionistProfile

        registry.register(PatientProfile, patient=lambda profile: profile.pk)
        for model in (DoctorProfile, LabTechProfile, PharmacistProfile, ReceptionistProfile):
            registry.register(model)
