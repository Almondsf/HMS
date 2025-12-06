from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    # UserRegistrationView,
    LoginView,
    # LogoutView,
    # UserViewSet
)

router = DefaultRouter()
# router.register(r'users', UserViewSet, basename='user')

app_name = 'authentication'

urlpatterns = [
    # Authentication endpoints
    # path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    # path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User endpoints (from router)
    path('', include(router.urls)),
]