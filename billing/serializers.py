from rest_framework import serializers

from . import services
from .models import MONEY, Invoice, InvoiceLine, Payment, ServiceItem


class ServiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceItem
        fields = ['id', 'code', 'name', 'category', 'price', 'charge_on', 'is_active']


class InvoiceLineSerializer(serializers.ModelSerializer):
    added_by_name = serializers.CharField(source='added_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = InvoiceLine
        fields = [
            'id', 'category', 'description', 'quantity', 'unit_price', 'amount', 'needs_price',
            'voided', 'void_reason', 'added_by_name', 'created_at',
        ]  # fmt: skip
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True, default=None)
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)
    amount = serializers.DecimalField(**MONEY, min_value=0)

    class Meta:
        model = Payment
        fields = [
            'id', 'receipt_number', 'invoice', 'invoice_number', 'amount', 'method', 'reference',
            'received_by_name', 'voided', 'void_reason', 'created_at',
        ]  # fmt: skip
        read_only_fields = ['receipt_number', 'voided', 'void_reason', 'created_at']

    def validate_method(self, method):
        if method == Payment.Method.INSURANCE:
            raise serializers.ValidationError('Insurance payments are recorded on the insurance claim.')
        return method

    def create(self, validated_data):
        return services.record_payment(by=self.context['request'].user, **validated_data)


class InvoiceSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    subtotal = serializers.DecimalField(**MONEY, read_only=True)
    total = serializers.DecimalField(**MONEY, read_only=True)
    amount_paid = serializers.DecimalField(**MONEY, read_only=True)
    balance = serializers.DecimalField(**MONEY, read_only=True)
    pending_insurance = serializers.DecimalField(**MONEY, read_only=True)
    patient_due = serializers.DecimalField(**MONEY, read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'number', 'patient', 'patient_name', 'patient_mrn', 'visit', 'status',
            'subtotal', 'discount', 'discount_reason', 'total', 'amount_paid', 'balance',
            'pending_insurance', 'patient_due',
            'issued_at', 'void_reason', 'created_at', 'lines', 'payments',
        ]  # fmt: skip
        read_only_fields = [
            'number', 'status', 'discount', 'discount_reason', 'issued_at', 'void_reason', 'created_at',
        ]  # fmt: skip

    def validate(self, attrs):
        visit = attrs.get('visit')
        if visit is not None and visit.patient_id != attrs['patient'].pk:
            raise serializers.ValidationError({'visit': "This visit belongs to another patient."})
        return attrs

    def create(self, validated_data):
        return services.create_invoice(patient=validated_data['patient'], visit=validated_data.get('visit'))


class ManualLineSerializer(serializers.Serializer):
    service_item = serializers.PrimaryKeyRelatedField(queryset=ServiceItem.objects.all(), required=False)
    description = serializers.CharField(required=False, allow_blank=True, default='', max_length=255)
    unit_price = serializers.DecimalField(**MONEY, min_value=0, required=False)
    quantity = serializers.IntegerField(min_value=1, default=1)


class PriceSerializer(serializers.Serializer):
    unit_price = serializers.DecimalField(**MONEY, min_value=0)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class DiscountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY, min_value=0)
    reason = serializers.CharField(max_length=255)
