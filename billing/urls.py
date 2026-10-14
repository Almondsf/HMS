from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DailySummaryView, InvoiceViewSet, PaymentViewSet, ServiceItemViewSet

router = DefaultRouter()
router.register(r'services', ServiceItemViewSet, basename='billing-services')
router.register(r'invoices', InvoiceViewSet, basename='invoices')
router.register(r'payments', PaymentViewSet, basename='payments')

urlpatterns = [
    path('summary/', DailySummaryView.as_view(), name='billing-summary'),
    path('', include(router.urls)),
]
