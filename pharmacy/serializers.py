from rest_framework import serializers

from clinical.models import Prescription

from . import services
from .models import DispensedItem, DispenseTransaction, Drug


class DrugSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Drug
        fields = [
            'id', 'name', 'description', 'unit', 'quantity_in_stock', 'reorder_level',
            'is_low_stock', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class DispensedItemSerializer(serializers.ModelSerializer):
    drug = serializers.PrimaryKeyRelatedField(queryset=Drug.objects.all())
    prescription = serializers.PrimaryKeyRelatedField(queryset=Prescription.objects.all())
    quantity_dispensed = serializers.IntegerField(min_value=1)

    class Meta:
        model = DispensedItem
        fields = ['id', 'drug', 'prescription', 'quantity_dispensed', 'notes']


class DispenseTransactionSerializer(serializers.ModelSerializer):
    items = DispensedItemSerializer(many=True)
    pharmacist_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = DispenseTransaction
        fields = ['id', 'dispensed_at', 'pharmacist_name', 'patient_name', 'items']

    def get_pharmacist_name(self, obj):
        return obj.pharmacist.user.get_full_name() if obj.pharmacist else None

    def get_patient_name(self, obj):
        return str(obj.patient) if obj.patient else None

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError('At least one dispensed item is required.')
        return items

    def create(self, validated_data):
        return services.dispense(pharmacist_user=self.context['request'].user, items=validated_data['items'])
