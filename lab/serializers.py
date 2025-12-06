from .models import Tests, TestOrder, TestResult
from rest_framework import serializers
from clinical.serializers import ConsultationSerializer

class TestsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tests
        fields = '__all__'

class TestOrderSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    ordered_by_name = serializers.SerializerMethodField()
    consultation = ConsultationSerializer(read_only=True)

    class Meta:
        model = TestOrder
        fields = [
            'id', 'patient_name', 'ordered_by_name',
            'consultation', 'ordered_at', 'is_completed'
        ]
    
    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name()
    
    def get_ordered_by_name(self, obj):
        return obj.ordered_by.user.get_full_name()



class TestResultSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)
    patient_name = serializers.SerializerMethodField()
    labtech_name = serializers.SerializerMethodField()

    class Meta:
        model = TestResult
        fields = [
            'id', 'order', 'test_name',
            'patient_name', 'labtech_name',
            'result_value', 'result_date', 'status', 'notes'
        ]
    
    def get_patient_name(self, obj):
        return obj.order.patient.user.get_full_name()

    def get_labtech_name(self, obj):
        return obj.performed_by.user.get_full_name()