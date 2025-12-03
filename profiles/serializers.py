from rest_framework import serializers
from .models import DoctorProfile, PatientProfile, LabTechProfile, PharmacistProfile, ReceptionistProfile
from authentication.serializers import UserRegistrationSerializer

class PatientSerializer(serializers.ModelSerializer):
    user = UserRegistrationSerializer()  # nested serializer for user

    class Meta:
        model = PatientProfile
        fields = '__all__'

    def create(self, validated_data):
        # Extract user data
        user_data = validated_data.pop('user')
        # Create user first
        user = UserRegistrationSerializer().create(user_data)
        # Create patient profile linked to user
        patient = PatientProfile.objects.create(user=user, **validated_data)
        return patient
    
class DoctorSerializer(serializers.ModelSerializer):
    user = UserRegistrationSerializer()  # nested serializer for user

    class Meta:
        model = DoctorProfile
        fields = '__all__'

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = UserRegistrationSerializer().create(user_data)
        doctor = DoctorProfile.objects.create(user=user, **validated_data)
        return doctor

class LabTechSerializer(serializers.ModelSerializer):
    user = UserRegistrationSerializer()  # nested serializer for user

    class Meta:
        model = LabTechProfile
        fields = '__all__'

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = UserRegistrationSerializer().create(user_data)
        lab_tech = LabTechProfile.objects.create(user=user, **validated_data)
        return lab_tech

class PharmacistSerializer(serializers.ModelSerializer):
    user = UserRegistrationSerializer()  # nested serializer for user

    class Meta:
        model = PharmacistProfile
        fields = '__all__'

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = UserRegistrationSerializer().create(user_data)
        pharmacist = PharmacistProfile.objects.create(user=user, **validated_data)
        return pharmacist

class ReceptionistSerializer(serializers.ModelSerializer):
    user = UserRegistrationSerializer()  # nested serializer for user

    class Meta:
        model = ReceptionistProfile
        fields = '__all__'

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = UserRegistrationSerializer().create(user_data)
        receptionist = ReceptionistProfile.objects.create(user=user, **validated_data)
        return receptionist