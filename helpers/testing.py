from itertools import count

from authentication.models import User
from profiles.models import (
    DoctorProfile, PatientProfile, LabTechProfile, PharmacistProfile, ReceptionistProfile
)

PROFILE_MODELS = {
    User.UserType.DOCTOR: DoctorProfile,
    User.UserType.PATIENT: PatientProfile,
    User.UserType.LAB_TECHNICIAN: LabTechProfile,
    User.UserType.PHARMACIST: PharmacistProfile,
    User.UserType.RECEPTIONIST: ReceptionistProfile,
}

TEST_PASSWORD = 'Str0ng-pass!'

_ids = count(1)


def make_user(user_type, **profile_fields):
    '''Create a user of the given role, plus its profile when the role has one.'''
    n = next(_ids)
    user = User.objects.create_user(
        first_name='Test', last_name=f'{user_type}{n}',
        email=f'{user_type}{n}@example.com', password=TEST_PASSWORD,
        user_type=user_type,
    )
    profile_model = PROFILE_MODELS.get(user_type)
    if profile_model:
        if user_type == User.UserType.DOCTOR:
            profile_fields.setdefault('specialty', 'General')
        profile_model.objects.create(user=user, **profile_fields)
    return user
