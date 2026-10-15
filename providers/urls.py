from django.urls import path

from . import views

urlpatterns = [
    path('', views.ProvidersView.as_view(), name='providers'),
    path('<str:channel>/', views.ChannelView.as_view(), name='provider-channel'),
    path('<str:channel>/<str:provider>/', views.ProviderView.as_view(), name='provider-config'),
    path('<str:channel>/<str:provider>/test/', views.ProviderTestView.as_view(), name='provider-test'),
]
