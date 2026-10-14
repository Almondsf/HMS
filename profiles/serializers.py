from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from authentication.models import User
from authentication.serializers import UserRegistrationSerializer

from . import services
from .models import (
    Department,
    DoctorProfile,
    LabTechProfile,
    NurseProfile,
    PatientProfile,
    PharmacistProfile,
    ReceptionistProfile,
)


class BaseProfileSerializer(serializers.ModelSerializer):
    '''
    Creates or updates a user and its profile together. Subclasses set
    `user_type`, so the role always matches the profile and can't be chosen
    by the client.
    '''

    user = UserRegistrationSerializer()
    user_type = None
    requires_login = True  # staff sign in, so they need an email and password

    def __init__(self, instance=None, *args, **kwargs):
        super().__init__(instance, *args, **kwargs)
        if instance is not None and not isinstance(instance, list | tuple) and hasattr(instance, 'user'):
            # Lets uniqueness checks on the nested user (email) ignore this user's own row
            self.fields['user'].instance = instance.user

    def validate(self, attrs):
        user = attrs.get('user', {})
        if self.requires_login and self.instance is None:
            missing = {field: 'This field is required.' for field in ('email', 'password') if not user.get(field)}
            if missing:
                raise serializers.ValidationError({'user': missing})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = UserRegistrationSerializer().create({**user_data, 'user_type': self.user_type})
        return self.Meta.model.objects.create(user=user, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user_data.pop('password', None)  # passwords change only through the password flows
        if user_data:
            for field, value in user_data.items():
                setattr(instance.user, field, value)
            instance.user.save()
        return super().update(instance, validated_data)


class PatientSerializer(BaseProfileSerializer):
    user_type = User.UserType.PATIENT
    requires_login = False

    mrn = serializers.CharField(
        max_length=20,
        required=False,
        validators=[UniqueValidator(PatientProfile.objects.all(), message='This MRN is already in use.')],
        help_text="Leave blank to auto-assign (<hospital prefix>-000123). Set it to keep a paper record's number.",
    )

    class Meta:
        model = PatientProfile
        fields = ['id', 'mrn', 'user', 'blood_group', 'genotype', 'allergies', 'medical_history', 'assigned_doctor']

    def validate_mrn(self, value):
        value = value.strip().upper()
        if self.instance is not None and value != self.instance.mrn:
            raise serializers.ValidationError("A patient's MRN can't be changed.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        validated_data['mrn'] = validated_data.get('mrn') or services.next_mrn()
        return super().create(validated_data)


class DoctorSerializer(BaseProfileSerializer):
    user_type = User.UserType.DOCTOR

    class Meta:
        model = DoctorProfile
        fields = '__all__'


class NurseSerializer(BaseProfileSerializer):
    user_type = User.UserType.NURSE

    class Meta:
        model = NurseProfile
        fields = '__all__'


class LabTechSerializer(BaseProfileSerializer):
    user_type = User.UserType.LAB_TECHNICIAN

    class Meta:
        model = LabTechProfile
        fields = '__all__'


class PharmacistSerializer(BaseProfileSerializer):
    user_type = User.UserType.PHARMACIST

    class Meta:
        model = PharmacistProfile
        fields = '__all__'


class ReceptionistSerializer(BaseProfileSerializer):
    user_type = User.UserType.RECEPTIONIST

    class Meta:
        model = ReceptionistProfile
        fields = '__all__'


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'is_active']


class StaffSerializer(serializers.ModelSerializer):
    '''A staff member as listed in the staff directory.'''

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role = serializers.CharField(source='user_type', read_only=True)
    department = serializers.SerializerMethodField()
    specialty = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'role', 'phone_number',
            'department', 'specialty', 'is_active', 'date_joined',
        ]  # fmt: skip
        read_only_fields = fields

    def _profile(self, user):
        for name in ('doctorprofile', 'nurseprofile'):
            profile = getattr(user, name, None)
            if profile is not None:
                return profile
        return None

    def get_department(self, user):
        profile = self._profile(user)
        department = getattr(profile, 'department', None)
        return {'id': department.id, 'name': department.name} if department else None

    def get_specialty(self, user):
        doctor = getattr(user, 'doctorprofile', None)
        return doctor.specialty if doctor else None
