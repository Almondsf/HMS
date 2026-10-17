from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from audit.recorder import Category, record

from . import password_reset, services, two_factor
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ResetPasswordSerializer,
    TwoFactorLoginSerializer,
    UserSerializer,
    session_for,
)
from .tokens import TenantTokenRefreshSerializer, check_token_tenant

# ---- Cookie mode (browsers) ----
#
# API clients send and receive the refresh token in the JSON body. Browsers
# opt into cookie mode with the X-HMS-Auth-Mode: cookie header: the refresh
# token then lives in an httpOnly cookie that page scripts can't read, so an
# injected script can't steal a long-lived session. The custom header doubles
# as CSRF protection: a cross-site form can't send it, and a cross-origin
# fetch that does is subject to the CORS allow-list.

AUTH_MODE_HEADER = 'X-HMS-Auth-Mode'


def cookie_mode(request):
    return request.headers.get(AUTH_MODE_HEADER, '').lower() == 'cookie'


def move_refresh_to_cookie(response):
    '''Take the refresh token out of the body and set it as an httpOnly cookie.'''
    refresh = response.data.pop('refresh', None)
    if refresh:
        response.set_cookie(
            settings.AUTH_REFRESH_COOKIE,
            refresh,
            max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            httponly=True,
            secure=settings.AUTH_REFRESH_COOKIE_SECURE,
            samesite='Lax',
            path=settings.AUTH_REFRESH_COOKIE_PATH,
        )
    return response


def clear_refresh_cookie(response):
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_REFRESH_COOKIE_PATH, samesite='Lax')
    return response


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return move_refresh_to_cookie(response) if cookie_mode(request) else response


class TenantTokenRefreshView(TokenRefreshView):
    serializer_class = TenantTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        if not cookie_mode(request):
            return super().post(request, *args, **kwargs)

        serializer = self.get_serializer(data={'refresh': request.COOKIES.get(settings.AUTH_REFRESH_COOKIE, '')})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc
        # Rotation issues a new refresh token: it replaces the cookie
        return move_refresh_to_cookie(Response(dict(serializer.validated_data), status=status.HTTP_200_OK))


class LogoutView(APIView):
    '''
    Revoke a refresh token so it can't be used to get new access tokens. In
    cookie mode the cookie itself proves the session (the access token may
    already have expired), and it is cleared.
    '''

    permission_classes = [AllowAny]
    serializer_class = LogoutSerializer

    def post(self, request):
        using_cookie = cookie_mode(request)
        if using_cookie:
            raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE, '')
        else:
            if not request.user.is_authenticated:
                return Response({'detail': 'Authentication credentials were not provided.'}, status=401)
            serializer = LogoutSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            raw = serializer.validated_data['refresh']

        try:
            token = RefreshToken(raw)
            check_token_tenant(token)
            if request.user.is_authenticated and str(token.get('user_id')) != str(request.user.id):
                raise TokenError('Token does not belong to this user')
            token.blacklist()
        except (TokenError, InvalidToken):
            record('logout_failed', Category.SECURITY)
            response = Response({'detail': 'Invalid or expired refresh token.'}, status=status.HTTP_400_BAD_REQUEST)
            return clear_refresh_cookie(response) if using_cookie else response

        record('logout', Category.SECURITY, metadata={'user_id': token.get('user_id')})
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        return clear_refresh_cookie(response) if using_cookie else response


class MeView(generics.RetrieveUpdateAPIView):
    '''The signed-in user's own account.'''

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    '''Change password and sign out every other session.'''

    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.must_change_password = False
        request.user.save(update_fields=['password', 'must_change_password'])
        services.revoke_all_sessions(request.user)
        record('password_changed', Category.SECURITY)
        return Response({'detail': 'Password changed. Please sign in again.'})


class ForgotPasswordView(APIView):
    """Email a reset link. Always answers the same way, so it can't reveal who has an account."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password_reset.request_reset(email=serializer.validated_data['email'], request=request)
        return Response({'detail': 'If that address has an account, a reset link is on its way.'})


class ResetPasswordView(APIView):
    """Set a new password from an emailed link (uid + token). Signs out every session."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password_reset.complete_reset(**serializer.validated_data)
        return Response({'detail': 'Password changed. You can sign in now.'})


# ---- Two-factor sign-in ----


def refused(detail, code):
    '''A 401 the web app can act on: {"detail": ..., "code": "challenge_expired"} etc.'''
    return Response({'detail': detail, 'code': code}, status=status.HTTP_401_UNAUTHORIZED)


class LoginTwoFactorView(APIView):
    '''Second step of signing in: the code from the authenticator app (or a recovery code).'''

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        data = TwoFactorLoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            user = two_factor.user_from_challenge(data.validated_data['challenge'])
        except DjangoValidationError as exc:
            return refused(exc.messages[0], 'challenge_expired')
        if services.is_locked_out(user):
            services.record_blocked_login(user)
            return refused('Too many failed login attempts. Try again later.', 'account_locked')
        if not two_factor.verify(user, data.validated_data['code']):
            services.record_failed_login(user.email)  # wrong codes count towards the lockout
            return refused('That code is not right. Use the current code from your app.', 'invalid_code')
        services.record_successful_login(user)
        response = Response(session_for(user))
        return move_refresh_to_cookie(response) if cookie_mode(request) else response


class TwoFactorCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)


class TwoFactorDisableSerializer(TwoFactorCodeSerializer):
    password = serializers.CharField(trim_whitespace=False)


class TwoFactorStatusView(APIView):
    '''Whether two-factor sign-in is on, and whether this account must use it.'''

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(two_factor.status(request.user))


class TwoFactorSetupView(APIView):
    '''Start: a QR code (and the key, to type in) for the authenticator app.'''

    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(two_factor.begin_setup(request.user))


class TwoFactorConfirmView(APIView):
    '''Finish: a code from the app turns it on. Returns the recovery codes, shown only this once.'''

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = TwoFactorCodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        codes = two_factor.confirm_setup(request.user, data.validated_data['code'])
        return Response({**two_factor.status(request.user), 'recovery_codes': codes})


class TwoFactorRecoveryCodesView(APIView):
    '''Replace the recovery codes (the old ones stop working).'''

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = TwoFactorCodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        codes = two_factor.new_recovery_codes(request.user, data.validated_data['code'])
        return Response({**two_factor.status(request.user), 'recovery_codes': codes})


class TwoFactorDisableView(APIView):
    '''Turn it off (not allowed for roles that must use it).'''

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = TwoFactorDisableSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        two_factor.disable(request.user, **data.validated_data)
        return Response(two_factor.status(request.user))
