from django.db import transaction
from rest_framework import serializers

from authentication.models import User
from authentication.serializers import UserRegistrationSerializer

from .models import DoctorProfile, LabTechProfile, PatientProfile, PharmacistProfile, ReceptionistProfile


class BaseProfileSerializer(serializers.ModelSerializer):
    '''
    Creates a user and its profile together. Subclasses set `user_type`,
    so the role always matches the profile and can't be chosen by the client.
    '''

    user = UserRegistrationSerializer()  # nested serializer for user
    user_type = None

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = UserRegistrationSerializer().create({**user_data, 'user_type': self.user_type})
        return self.Meta.model.objects.create(user=user, **validated_data)


class PatientSerializer(BaseProfileSerializer):
    user_type = User.UserType.PATIENT

    class Meta:
        model = PatientProfile
        fields = '__all__'


class DoctorSerializer(BaseProfileSerializer):
    user_type = User.UserType.DOCTOR

    class Meta:
        model = DoctorProfile
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
