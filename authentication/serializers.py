from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenObtainSerializer
from rest_framework_simplejwt.settings import api_settings

from . import services, two_factor
from .tokens import add_tenant_claim

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    '''
    Personal details only. Role and privilege fields (user_type, is_staff,
    is_admin, is_superuser, is_active) are deliberately not accepted here;
    the role is set by the profile serializer that creates the user.
    '''

    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
        style={'input_type': 'password'},
        help_text='Required for staff. Patients without one simply cannot sign in.',
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'password',
            'first_name',
            'last_name',
            'user_type',
            'gender',
            'date_of_birth',
            'phone_number',
            'address',
            'emergency_contact',
            'emergency_phone',
        ]
        read_only_fields = ['id', 'user_type']

    def validate_email(self, value):
        return value or None  # blank -> NULL, so many email-less patients don't clash

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    '''The signed-in user's own account details.'''

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    # True only on the platform site, for its superusers: opens the operator dashboard
    is_platform_operator = serializers.SerializerMethodField()
    two_factor = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'user_type',
            'gender',
            'date_of_birth',
            'phone_number',
            'address',
            'emergency_contact',
            'emergency_phone',
            'last_login',
            'date_joined',
            'must_change_password',
            'is_platform_operator',
            'two_factor',
        ]
        read_only_fields = ['id', 'email', 'user_type', 'last_login', 'date_joined', 'must_change_password']

    def get_two_factor(self, user):
        # {enabled, required, recovery_codes_left}; the app insists on setup when required and not enabled
        return two_factor.status(user)

    def get_is_platform_operator(self, user):
        from django.db import connection
        from django_tenants.utils import get_public_schema_name

        return user.is_superuser and connection.schema_name == get_public_schema_name()


class LoginSerializer(TokenObtainPairSerializer):
    """
    Serializer for user login
    Handles email/password authentication and returns JWT tokens
    """

    default_error_messages = {
        **TokenObtainPairSerializer.default_error_messages,
        'locked': 'Too many failed login attempts. Try again later.',
    }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims to JWT token payload
        token['email'] = user.email
        token['user_type'] = user.user_type
        token['full_name'] = user.get_full_name()

        return add_tenant_claim(token)

    def validate(self, attrs):
        email = attrs.get(self.username_field, '')

        # Locked accounts are refused even with the right password. Failed and
        # successful attempts are counted by the authentication backend.
        user = User.objects.filter(email__iexact=email).first()
        if user and services.is_locked_out(user):
            services.record_blocked_login(user)
            raise AuthenticationFailed(self.error_messages['locked'], 'account_locked')

        TokenObtainSerializer.validate(self, attrs)  # checks the password, sets self.user
        if two_factor.is_enabled(self.user):
            # No tokens yet: the code comes next (POST login/verify/ with this challenge)
            return {'two_factor_required': True, 'challenge': two_factor.challenge_for(self.user)}
        return session_for(self.user)


def session_for(user):
    '''Tokens for a fully signed-in user, plus what the web app needs immediately.'''
    refresh = LoginSerializer.get_token(user)
    if api_settings.UPDATE_LAST_LOGIN:
        update_last_login(None, user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_type': user.user_type,
            'must_change_password': user.must_change_password,
        },
    }


class TwoFactorLoginSerializer(serializers.Serializer):
    challenge = serializers.CharField()
    code = serializers.CharField(max_length=20)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context['request'].user)
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
