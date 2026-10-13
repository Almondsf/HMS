from django.core.exceptions import PermissionDenied
from rest_framework import serializers

from authentication.models import User

from . import services
from .models import LabTest, TestOrder, TestResult


def full_name(profile):
    return profile.user.get_full_name() if profile else None


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ['id', 'name', 'description', 'normal_range', 'cost', 'is_active']


class TestResultSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source='test.name', read_only=True)
    normal_range = serializers.CharField(source='test.normal_range', read_only=True)
    labtech_name = serializers.SerializerMethodField()

    class Meta:
        model = TestResult
        fields = [
            'id', 'order', 'test', 'test_name', 'normal_range', 'status',
            'result_value', 'notes', 'labtech_name', 'completed_at',
        ]
        read_only_fields = ['order', 'test', 'completed_at']

    def get_labtech_name(self, obj):
        return full_name(obj.labtech)

    def update(self, instance, validated_data):
        return services.record_result(
            result=instance, labtech_user=self.context['request'].user, **validated_data
        )


class TestOrderSerializer(serializers.ModelSerializer):
    tests = serializers.PrimaryKeyRelatedField(queryset=LabTest.objects.all(), many=True, write_only=True)
    results = TestResultSerializer(many=True, read_only=True)
    patient_name = serializers.SerializerMethodField()
    ordered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TestOrder
        fields = [
            'id', 'patient', 'patient_name', 'consultation', 'ordered_by_name',
            'reason', 'status', 'ordered_at', 'tests', 'results',
        ]
        read_only_fields = ['status', 'ordered_at']
        extra_kwargs = {'patient': {'required': False}}

    def get_patient_name(self, obj):
        return full_name(obj.patient)

    def get_ordered_by_name(self, obj):
        return full_name(obj.ordered_by)

    def validate(self, attrs):
        consultation = attrs.get('consultation')
        if consultation and 'patient' not in attrs:
            attrs['patient'] = consultation.visit.patient
        if 'patient' not in attrs:
            raise serializers.ValidationError({'patient': 'Give a patient or a consultation.'})
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        consultation = validated_data.get('consultation')
        ordered_by = None
        if user.user_type == User.UserType.DOCTOR:
            ordered_by = user.doctorprofile
            if consultation and consultation.visit.assigned_doctor_id != ordered_by.id:
                raise PermissionDenied('You can only order tests for your own consultations.')
        return services.place_order(ordered_by=ordered_by, **validated_data)
