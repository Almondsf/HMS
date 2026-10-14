import re
import secrets
from zoneinfo import available_timezones

from rest_framework import serializers

from subscriptions.models import Subscription
from subscriptions.services import describe

from . import services
from .features import features_for
from .models import Hospital


class HospitalSettingsValidation:
    '''Validation shared by the platform API and the hospital's own settings.'''

    def validate_timezone(self, value):
        if value not in available_timezones():
            raise serializers.ValidationError('Unknown timezone. Use an IANA name such as Africa/Lagos.')
        return value

    def validate_currency(self, value):
        if not re.fullmatch(r'[A-Z]{3}', value):
            raise serializers.ValidationError('Use a 3-letter ISO 4217 code, e.g. NGN.')
        return value

    def validate_mrn_prefix(self, value):
        if not re.fullmatch(r'[A-Z0-9]{1,10}', value):
            raise serializers.ValidationError('Use 1-10 capital letters or digits.')
        return value


class HospitalSettingsSerializer(HospitalSettingsValidation, serializers.ModelSerializer):
    '''A hospital's own settings, as seen and edited by its staff.'''

    domain = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = Hospital
        fields = [
            'name', 'domain', 'plan', 'features', 'contact_email', 'phone', 'address',
            'timezone', 'currency', 'mrn_prefix', 'subscription',
        ]  # fmt: skip
        read_only_fields = ['plan']

    def get_domain(self, obj):
        primary = obj.domains.filter(is_primary=True).first()
        return primary.domain if primary else None

    def get_features(self, obj):
        return sorted(features_for(obj))

    def get_subscription(self, obj):
        # Drives the app's renewal banner and read-only notice
        subscription = Subscription.objects.filter(hospital=obj).first()
        return describe(subscription) if subscription else None


class PlatformHospitalSerializer(HospitalSettingsSerializer):
    '''Everything about a hospital, for platform operators.'''

    domains = serializers.SlugRelatedField(many=True, read_only=True, slug_field='domain')

    class Meta(HospitalSettingsSerializer.Meta):
        fields = ['id', 'schema_name', 'domains', 'is_active', 'created_at', *HospitalSettingsSerializer.Meta.fields]
        read_only_fields = ['schema_name', 'created_at']


class HospitalProvisionSerializer(HospitalSettingsValidation, serializers.Serializer):
    name = serializers.CharField(max_length=150)
    schema_name = serializers.CharField(help_text='Permanent identifier, e.g. stlukes')
    domain = serializers.CharField(required=False, help_text='Defaults to <schema_name>.<TENANT_BASE_DOMAIN>')
    plan = serializers.ChoiceField(choices=Hospital.Plan.choices, default=Hospital.Plan.BASIC)
    contact_email = serializers.EmailField(required=False, default='')
    admin_email = serializers.EmailField()
    admin_first_name = serializers.CharField(max_length=30)
    admin_last_name = serializers.CharField(max_length=30)
    admin_password = serializers.CharField(
        write_only=True, required=False, help_text='Omit to generate one, returned once in the response'
    )

    def create(self, validated_data):
        self.generated_password = None
        if 'admin_password' not in validated_data:
            self.generated_password = validated_data['admin_password'] = secrets.token_urlsafe(16)
        hospital, self.admin = services.provision_hospital(**validated_data)
        return hospital

    def to_representation(self, hospital):
        data = PlatformHospitalSerializer(hospital).data
        data['admin'] = {'email': self.admin.email}
        if self.generated_password:
            data['admin']['temporary_password'] = self.generated_password
        return data


class ManualPaymentSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=Hospital.Plan.choices)
    interval = serializers.ChoiceField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    reference = serializers.CharField(max_length=80, help_text='e.g. the bank transfer reference')
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
