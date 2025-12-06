from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        # fields = ['']  # include all fields from the User model
        exclude = ['groups', 'user_permissions']

    def create(self, validated_data):
        # Extract password to hash it
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user

class LoginSerializer(TokenObtainPairSerializer):
    """
    Serializer for user login
    Handles email/password authentication and returns JWT tokens
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims to JWT token payload
        token['email'] = user.email
        token['user_type'] = user.user_type
        token['full_name'] = f"{user.first_name} {user.last_name}"
        
        return token
    
    def validate(self, attrs):
        """
        Override to add user information to login response
        """
        data = super().validate(attrs)
        
        # Add user info to response (frontend needs this immediately)
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'user_type': self.user.user_type,
        }
        
        return data


# class UserSerializer(serializers.ModelSerializer):
#     """
#     Serializer for user details (read operations)
#     Used for retrieving user information
#     """
#     full_name = serializers.SerializerMethodField()
#     user_type_display = serializers.CharField(source='get_user_type_display', read_only=True)
    
#     class Meta:
#         model = User
#         fields = (
#             'id', 'email', 'first_name', 'last_name', 'full_name',
#             'user_type', 'user_type_display', 'phone_number',
#             'is_active', 'date_joined', 'last_login'
#         )
#         read_only_fields = (
#             'id', 'date_joined', 'last_login', 'is_active'
#         )
    
#     def get_full_name(self, obj):
#         """Custom method field to get full name"""
#         return f"{obj.first_name} {obj.last_name}".strip()


# class UserUpdateSerializer(serializers.ModelSerializer):
#     """
#     Serializer for updating user profile
#     Excludes sensitive fields like password and user_type
#     """
#     class Meta:
#         model = User
#         fields = (
#             'first_name', 'last_name', 'phone_number'
#         )
    
#     def validate_phone_number(self, value):
#         """
#         Custom validation for phone number
#         Ensure it's not already taken by another user
#         """
#         user = self.context['request'].user
#         if User.objects.exclude(pk=user.pk).filter(phone_number=value).exists():
#             raise serializers.ValidationError("This phone number is already in use.")
#         return value


# class ChangePasswordSerializer(serializers.Serializer):
#     """
#     Serializer for password change endpoint
#     Requires old password and validates new password
#     """
#     old_password = serializers.CharField(
#         required=True,
#         write_only=True,
#         style={'input_type': 'password'}
#     )
#     new_password = serializers.CharField(
#         required=True,
#         write_only=True,
#         validators=[validate_password],
#         style={'input_type': 'password'}
#     )
#     new_password2 = serializers.CharField(
#         required=True,
#         write_only=True,
#         style={'input_type': 'password'},
#         label="Confirm New Password"
#     )
    
#     def validate_old_password(self, value):
#         """Validate that old password is correct"""
#         user = self.context['request'].user
#         if not user.check_password(value):
#             raise serializers.ValidationError("Old password is incorrect.")
#         return value
    
#     def validate(self, attrs):
#         """Validate that new passwords match"""
#         if attrs['new_password'] != attrs['new_password2']:
#             raise serializers.ValidationError({
#                 "new_password": "New password fields didn't match."
#             })
#         return attrs
    
#     def save(self, **kwargs):
#         """Update user's password"""
#         user = self.context['request'].user
#         user.set_password(self.validated_data['new_password'])
#         user.save()
#         return user

# class UserListSerializer(serializers.ModelSerializer):
#     """
#     Minimal serializer for listing users
#     Used in dropdowns, selections, etc.
#     """
#     display_name = serializers.SerializerMethodField()
    
#     class Meta:
#         model = User
#         fields = ('id', 'email', 'display_name', 'user_type')
    
#     def get_display_name(self, obj):
#         full_name = f"{obj.first_name} {obj.last_name}".strip()
#         return f"{full_name} ({obj.get_user_type_display()})"