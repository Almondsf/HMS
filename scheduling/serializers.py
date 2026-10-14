from rest_framework import serializers

from . import services
from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(default=15, help_text='5-240 minutes')
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'patient_mrn', 'doctor', 'doctor_name', 'department',
            'starts_at', 'ends_at', 'duration_minutes', 'reason', 'status', 'cancellation_reason',
            'visit', 'created_at',
        ]  # fmt: skip
        read_only_fields = ['ends_at', 'status', 'cancellation_reason', 'visit', 'created_at']

    def to_representation(self, appointment):
        data = super().to_representation(appointment)
        data['duration_minutes'] = appointment.duration_minutes
        return data

    def create(self, validated_data):
        return services.book_appointment(booked_by=self.context['request'].user, **validated_data)

    def update(self, appointment, validated_data):
        '''Reschedule (time or length) or edit the reason; patient and doctor are fixed.'''
        for field in ('patient', 'doctor'):
            if field in validated_data and validated_data[field] != getattr(appointment, field):
                raise serializers.ValidationError({field: 'Cancel and book a new appointment instead.'})
        if 'starts_at' in validated_data or 'duration_minutes' in self.initial_data:
            services.reschedule_appointment(
                appointment=appointment,
                starts_at=validated_data.get('starts_at'),
                duration_minutes=validated_data.get('duration_minutes'),
            )
        for field in ('reason', 'department'):
            if field in validated_data:
                setattr(appointment, field, validated_data[field])
        appointment.save()
        return appointment


class CancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')
