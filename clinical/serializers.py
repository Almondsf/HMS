from rest_framework import serializers
from .models import Consultation, Visit, Prescription, LabTestOrder

 
        

class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = '__all__'
        read_only_fields = ('consultation',)
        
class LabTestOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTestOrder
        fields = '__all__'
        read_only_fields = ('consultation',)
        
class ConsultationSerializer(serializers.ModelSerializer):
    prescriptions = PrescriptionSerializer(many=True, required=False)
    lab_orders = LabTestOrderSerializer(many=True, required=False)

    class Meta:
        model = Consultation
        fields = [
            'id', 'visit', 'subjective', 'objective', 'assessment',
            'plan', 'follow_up_date', 'prescriptions', 'lab_orders'
        ]

    def create(self, validated_data):
        prescriptions_data = validated_data.pop('prescriptions', [])
        lab_orders_data = validated_data.pop('lab_orders', [])
        consultation = Consultation.objects.create(**validated_data)

        # Create multiple prescriptions
        for prescription in prescriptions_data:
            Prescription.objects.create(consultation=consultation, **prescription)

        # Create multiple lab orders
        for lab_order in lab_orders_data:
            LabTestOrder.objects.create(consultation=consultation, **lab_order)

        return consultation

        
class VisitSerializer(serializers.ModelSerializer):
    consultations = ConsultationSerializer(many=True, read_only=True)

    class Meta:
        model = Visit
        fields = ['id', 'patient', 'assigned_doctor', 'visit_date', 'reason_for_visit', 'consultations']
       