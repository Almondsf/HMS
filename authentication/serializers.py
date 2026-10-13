from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from . import services

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    '''
    Personal details only. Role and privilege fields (user_type, is_staff,
    is_admin, is_superuser, is_active) are deliberately not accepted here;
    the role is set by the profile serializer that creates the user.
    '''
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'id', 'email', 'password', 'first_name', 'last_name', 'user_type',
            'gender', 'date_of_birth', 'phone_number', 'address',
            'emergency_contact', 'emergency_phone',
        ]
        read_only_fields = ['id', 'user_type']

    def create(self, validated_data):
        # Extract password to hash it
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    '''The signed-in user's own account details.'''
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'user_type',
            'gender', 'date_of_birth', 'phone_number', 'address',
            'emergency_contact', 'emergency_phone', 'last_login', 'date_joined',
        ]
        read_only_fields = ['id', 'email', 'user_type', 'last_login', 'date_joined']


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

        return token

    def validate(self, attrs):
        email = attrs.get(self.username_field, '')

        # Locked accounts are refused even with the right password
        user = User.objects.filter(email__iexact=email).first()
        if user and services.is_locked_out(user):
            raise AuthenticationFailed(self.error_messages['locked'], 'account_locked')

        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            services.record_failed_login(email)
            raise

        services.record_successful_login(self.user)

        # Add user info to response (frontend needs this immediately)
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'user_type': self.user.user_type,
        }

        return data


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
