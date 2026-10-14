from django.urls import path

from . import views

urlpatterns = [
    path('', views.SignupView.as_view(), name='signup'),
    path('availability/', views.AvailabilityView.as_view(), name='signup-availability'),
    path('plans/', views.PlansView.as_view(), name='signup-plans'),
    path('verify/', views.VerifyView.as_view(), name='signup-verify'),
    path('status/', views.StatusView.as_view(), name='signup-status'),
]
