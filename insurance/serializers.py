from rest_framework import serializers

from billing.models import MONEY

from . import services
from .models import Claim, Coverage, InsuranceProvider


class InsuranceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceProvider
        fields = [
            'id', 'name', 'code', 'kind', 'phone', 'email', 'address',
            'default_coverage_percent', 'requires_authorization', 'is_active',
        ]  # fmt: skip


class CoverageSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    effective_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Coverage
        fields = [
            'id', 'patient', 'provider', 'provider_name', 'member_number', 'plan_name',
            'coverage_percent', 'effective_percent', 'valid_from', 'valid_to', 'is_active',
        ]  # fmt: skip

    def validate(self, attrs):
        valid_from = attrs.get('valid_from', getattr(self.instance, 'valid_from', None))
        valid_to = attrs.get('valid_to', getattr(self.instance, 'valid_to', None))
        if valid_to and valid_from and valid_to < valid_from:
            raise serializers.ValidationError({'valid_to': 'Must be on or after valid_from.'})
        return attrs


class ClaimSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='coverage.provider.name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)
    patient_name = serializers.CharField(source='invoice.patient.user.get_full_name', read_only=True)

    class Meta:
        model = Claim
        fields = [
            'id', 'number', 'invoice', 'invoice_number', 'patient_name', 'coverage', 'provider_name',
            'status', 'claimed_amount', 'approved_amount', 'paid_amount', 'authorization_code',
            'rejection_reason', 'notes', 'submitted_at', 'responded_at', 'paid_at', 'created_at',
        ]  # fmt: skip
        read_only_fields = [
            'number', 'status', 'claimed_amount', 'approved_amount', 'paid_amount', 'rejection_reason',
            'submitted_at', 'responded_at', 'paid_at', 'created_at',
        ]  # fmt: skip

    def create(self, validated_data):
        claim = services.create_claim(
            invoice=validated_data['invoice'],
            coverage=validated_data['coverage'],
            authorization_code=validated_data.get('authorization_code', ''),
        )
        if validated_data.get('notes'):
            claim.notes = validated_data['notes']
            claim.save(update_fields=['notes', 'updated_at'])
        return claim

    def update(self, claim, validated_data):
        # Only bookkeeping fields change by PATCH; money moves through the actions
        for field in ('notes', 'authorization_code'):
            if field in validated_data:
                setattr(claim, field, validated_data[field])
        claim.save()
        return claim


class ClaimResponseSerializer(serializers.Serializer):
    approved_amount = serializers.DecimalField(**MONEY, required=False, min_value=0)
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default='', max_length=255)

    def validate(self, attrs):
        if bool(attrs.get('approved_amount')) == bool(attrs.get('rejection_reason')):
            raise serializers.ValidationError('Give either approved_amount or rejection_reason.')
        return attrs


class ClaimPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY, min_value=0)
    reference = serializers.CharField(required=False, allow_blank=True, default='', max_length=100)
