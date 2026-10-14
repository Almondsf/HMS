from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profiles'

    def ready(self):
        from audit import registry

        from .models import (
            CashierProfile,
            Department,
            DoctorProfile,
            LabTechProfile,
            NurseProfile,
            PatientProfile,
            PharmacistProfile,
            ReceptionistProfile,
        )

        registry.register(PatientProfile, patient=lambda profile: profile.pk)
        for model in (
            Department,
            DoctorProfile,
            NurseProfile,
            LabTechProfile,
            PharmacistProfile,
            ReceptionistProfile,
            CashierProfile,
        ):
            registry.register(model)
