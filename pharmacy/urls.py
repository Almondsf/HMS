from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DrugViewSet, DispenseTransactionViewSet

router = DefaultRouter()
router.register(r'drugs', DrugViewSet)
router.register(r'dispense-transactions', DispenseTransactionViewSet)
# router.register(r'dispensed-items', DispensedItemViewSet)
urlpatterns = [
    path('', include(router.urls)),
]