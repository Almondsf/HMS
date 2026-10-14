from rest_framework import serializers

from lab.models import LabTest
from lab.serializers import TestOrderSerializer
from pharmacy.models import Drug

from . import services
from .models import Consultation, Prescription, Visit


class PrescriptionSerializer(serializers.ModelSerializer):
    drug = serializers.PrimaryKeyRelatedField(queryset=Drug.objects.all(), required=False, allow_null=True)
    quantity_dispensed = serializers.IntegerField(read_only=True)

    class Meta:
        model = Prescription
        fields = [
            'id',
            'drug',
            'medication_name',
            'dosage',
            'frequency',
            'duration',
            'quantity',
            'quantity_dispensed',
            'instructions',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def validate(self, attrs):
        if not (attrs.get('drug') or attrs.get('medication_name')):
            raise serializers.ValidationError({'medication_name': 'Choose a drug or enter a medication name.'})
        return attrs


class PrescriptionDetailSerializer(PrescriptionSerializer):
    '''Prescription with patient context, for the pharmacy queue.'''

    patient = serializers.IntegerField(source='consultation.visit.patient_id', read_only=True)
    patient_name = serializers.CharField(source='consultation.visit.patient.user.get_full_name', read_only=True)
    prescribed_by = serializers.CharField(
        source='consultation.visit.assigned_doctor.user.get_full_name', read_only=True
    )

    class Meta(PrescriptionSerializer.Meta):
        fields = ['consultation', 'patient', 'patient_name', 'prescribed_by', *PrescriptionSerializer.Meta.fields]


class ConsultationSerializer(serializers.ModelSerializer):
    prescriptions = PrescriptionSerializer(many=True, required=False)
    lab_tests = serializers.PrimaryKeyRelatedField(
        queryset=LabTest.objects.all(),
        many=True,
        write_only=True,
        required=False,
        help_text='Lab tests to order with this consultation.',
    )
    lab_reason = serializers.CharField(write_only=True, required=False, allow_blank=True)
    lab_orders = TestOrderSerializer(many=True, read_only=True)

    class Meta:
        model = Consultation
        fields = [
            'id',
            'visit',
            'subjective',
            'objective',
            'assessment',
            'plan',
            'follow_up_date',
            'prescriptions',
            'lab_tests',
            'lab_reason',
            'lab_orders',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        return services.record_consultation(doctor_user=self.context['request'].user, **validated_data)

    def update(self, instance, validated_data):
        if 'visit' in validated_data and validated_data['visit'] != instance.visit:
            raise serializers.ValidationError({'visit': "A consultation can't be moved to another visit."})
        if {'prescriptions', 'lab_tests'} & validated_data.keys():
            raise serializers.ValidationError(
                'Prescriptions and lab tests can only be added when the consultation is created.'
            )
        validated_data.pop('lab_reason', None)
        return super().update(instance, validated_data)


class VisitValidation:
    def validate_assigned_doctor(self, doctor):
        if not doctor.user.is_active:
            raise serializers.ValidationError('This doctor is no longer active.')
        return doctor

    def validate_patient(self, patient):
        if not patient.user.is_active:
            raise serializers.ValidationError("This patient's record is deactivated.")
        return patient


class VisitSerializer(VisitValidation, serializers.ModelSerializer):
    consultations = ConsultationSerializer(many=True, read_only=True)

    class Meta:
        model = Visit
        fields = ['id', 'patient', 'assigned_doctor', 'visit_date', 'reason_for_visit', 'status', 'consultations']


class VisitSummarySerializer(VisitValidation, serializers.ModelSerializer):
    '''Visit without clinical notes, for front-desk staff.'''

    class Meta:
        model = Visit
        fields = ['id', 'patient', 'assigned_doctor', 'visit_date', 'reason_for_visit', 'status']
