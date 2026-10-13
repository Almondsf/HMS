from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DispenseTransactionViewSet, DrugViewSet

router = DefaultRouter()
router.register(r'drugs', DrugViewSet)
router.register(r'dispense-transactions', DispenseTransactionViewSet)
# router.register(r'dispensed-items', DispensedItemViewSet)
urlpatterns = [
    path('', include(router.urls)),
]
