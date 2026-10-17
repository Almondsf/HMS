from django.urls import path

from .views import (
    ChangePasswordView,
    ForgotPasswordView,
    LoginTwoFactorView,
    LoginView,
    LogoutView,
    MeView,
    ResetPasswordView,
    TenantTokenRefreshView,
    TwoFactorConfirmView,
    TwoFactorDisableView,
    TwoFactorRecoveryCodesView,
    TwoFactorSetupView,
    TwoFactorStatusView,
)

app_name = 'authentication'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('login/verify/', LoginTwoFactorView.as_view(), name='login_two_factor'),
    path('two-factor/', TwoFactorStatusView.as_view(), name='two_factor'),
    path('two-factor/setup/', TwoFactorSetupView.as_view(), name='two_factor_setup'),
    path('two-factor/confirm/', TwoFactorConfirmView.as_view(), name='two_factor_confirm'),
    path('two-factor/recovery-codes/', TwoFactorRecoveryCodesView.as_view(), name='two_factor_recovery_codes'),
    path('two-factor/disable/', TwoFactorDisableView.as_view(), name='two_factor_disable'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TenantTokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('password/change/', ChangePasswordView.as_view(), name='password_change'),
    path('password/forgot/', ForgotPasswordView.as_view(), name='password_forgot'),
    path('password/reset/', ResetPasswordView.as_view(), name='password_reset'),
]
