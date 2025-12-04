from .models import DispenseTransaction, DispensedItem, Drug
from rest_framework import serializers
from clinical.serializers import ConsultationSerializer, PrescriptionSerializer
from profiles.serializers import PharmacistSerializer
from django.db import transaction

class DrugSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drug
        fields = '__all__'
        
    
       
class DispensedItemSerializer(serializers.ModelSerializer):
    drug = serializers.PrimaryKeyRelatedField(queryset=Drug.objects.all()) 
    
    class Meta:
        model = DispensedItem
        fields = ['id', 'drug', 'quantity_dispensed',]
        
    def validate(self, data):
        drug = data['drug']
        qty = data['quantity_dispensed']

        if qty > drug.quantity_in_stock:
            raise serializers.ValidationError(
                f"Insufficient stock for {drug.name}. "
                f"Available: {drug.quantity_in_stock}, Requested: {qty}"
            )
            

        return data
    
    
class DispenseTransactionSerializer(serializers.ModelSerializer):
    items = DispensedItemSerializer(many=True)
    prescription = PrescriptionSerializer(read_only=True)
    pharmacist = PharmacistSerializer(read_only=True)

    class Meta:
        model = DispenseTransaction
        fields = ['id', 'prescription', 'pharmacist', 'dispensed_at', 'items']
        
    def validate(self, data):
        if not data.get('items'):
            raise serializers.ValidationError("At least one dispensed item is required.")
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        pharmacist = self.context['request'].user.pharmacist
        prescription = self.context['prescription']

        transaction_instance = DispenseTransaction.objects.create(
            pharmacist=pharmacist,
            prescription=prescription,
            **validated_data
        )

        for item in items_data:
            drug = item['drug']
            qty = item['quantity_dispensed']
            
            drug.quantity_in_stock -= qty
            drug.save()
            
            # Create item
            DispensedItem.objects.create(
                transaction=transaction_instance,
                prescription=prescription,
                **item
            )
            

        return transaction_instance
