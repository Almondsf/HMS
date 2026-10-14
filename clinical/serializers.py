from rest_framework import serializers

from authentication.models import User
from lab.models import LabTest
from lab.serializers import TestOrderSerializer
from pharmacy.models import Drug

from . import services
from . import vitals as vitals_rules
from .models import Consultation, Prescription, Visit, VitalSigns


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


class VitalSignsSerializer(serializers.ModelSerializer):
    bmi = serializers.FloatField(read_only=True)
    flags = serializers.SerializerMethodField()
    is_critical = serializers.SerializerMethodField()
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = VitalSigns
        fields = [
            'id', 'visit', 'recorded_at', 'recorded_by_name', *vitals_rules.MEASUREMENTS,
            'bmi', 'flags', 'is_critical', 'notes',
        ]  # fmt: skip
        read_only_fields = ['recorded_at']

    def _assessment(self, vitals):
        return vitals_rules.assess({field: getattr(vitals, field) for field in vitals_rules.MEASUREMENTS})

    def get_flags(self, vitals):
        return self._assessment(vitals)[0]

    def get_is_critical(self, vitals):
        return self._assessment(vitals)[1]

    def validate_visit(self, visit):
        user = self.context['request'].user
        if user.user_type == User.UserType.DOCTOR and visit.assigned_doctor.user_id != user.id:
            raise serializers.ValidationError("You can only record vitals for your own patients' visits.")
        return visit

    def create(self, validated_data):
        return services.record_vitals(by=self.context['request'].user, **validated_data)


class TriageSerializer(serializers.Serializer):
    triage_level = serializers.ChoiceField(choices=Visit.Triage.choices)
    triage_notes = serializers.CharField(required=False, allow_blank=True, default='')


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
    vitals = VitalSignsSerializer(many=True, read_only=True)

    class Meta:
        model = Visit
        fields = [
            'id', 'patient', 'assigned_doctor', 'visit_date', 'reason_for_visit', 'status',
            'triage_level', 'triage_notes', 'triaged_at', 'vitals', 'consultations',
        ]  # fmt: skip
        # Status changes via the start / complete / cancel actions, triage via the triage action
        read_only_fields = ['status', 'triage_level', 'triage_notes', 'triaged_at']


class VisitSummarySerializer(VisitValidation, serializers.ModelSerializer):
    '''Visit without clinical notes, for front-desk staff.'''

    class Meta:
        model = Visit
        fields = ['id', 'patient', 'assigned_doctor', 'visit_date', 'reason_for_visit', 'status', 'triage_level']
        read_only_fields = ['status', 'triage_level']


class QueueEntrySerializer(serializers.ModelSerializer):
    '''A patient in a doctor's queue (no clinical notes).'''

    position = serializers.IntegerField(read_only=True)
    waiting_minutes = serializers.SerializerMethodField()
    patient = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    appointment_time = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = [
            'id', 'position', 'status', 'triage_level', 'patient', 'doctor', 'reason_for_visit',
            'visit_date', 'waiting_minutes', 'appointment_time',
        ]  # fmt: skip

    def get_waiting_minutes(self, visit):
        return int((self.context['now'] - visit.visit_date).total_seconds() // 60)

    def get_patient(self, visit):
        return {'id': visit.patient_id, 'mrn': visit.patient.mrn, 'name': visit.patient.user.get_full_name()}

    def get_doctor(self, visit):
        return {'id': visit.assigned_doctor_id, 'name': visit.assigned_doctor.user.get_full_name()}

    def get_appointment_time(self, visit):
        appointment = getattr(visit, 'appointment', None)
        return appointment.starts_at if appointment else None
