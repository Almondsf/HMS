'''
JWTs are bound to the hospital that issued them.

Each hospital has its own users table, so user #5 at one hospital is a
different person from user #5 at another. A token only carries a user id,
so without this binding a token from hospital A would authenticate as a
stranger at hospital B. Every token gets a `tenant` claim at login and is
rejected anywhere else.
'''

from django.db import connection
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

TENANT_CLAIM = 'tenant'


def add_tenant_claim(token):
    token[TENANT_CLAIM] = connection.schema_name
    return token


def check_token_tenant(token):
    if token.get(TENANT_CLAIM) != connection.schema_name:
        raise InvalidToken('Token was not issued for this hospital.')


# Reachable before two-factor setup: sign-in, "me", password and two-factor endpoints
SETUP_ALLOWED_PATHS = ('/api/v1/auth/', '/api/auth/')


class TwoFactorSetupRequired(PermissionDenied):
    default_detail = 'Set up two-factor sign-in to continue.'
    default_code = 'two_factor_setup_required'


class TenantJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None and not request.path.startswith(SETUP_ALLOWED_PATHS):
            from . import two_factor

            if two_factor.setup_required(result[0]):
                raise TwoFactorSetupRequired
        return result

    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        check_token_tenant(token)
        return token


class TenantTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            check_token_tenant(self.token_class(attrs['refresh']))
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc
        return super().validate(attrs)
