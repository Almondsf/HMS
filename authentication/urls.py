from django.urls import path

from .views import ChangePasswordView, LoginView, LogoutView, MeView, TenantTokenRefreshView

app_name = 'authentication'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TenantTokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('password/change/', ChangePasswordView.as_view(), name='password_change'),
]
