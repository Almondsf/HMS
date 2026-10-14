from django.urls import path

from .views import CancelView, CheckoutView, ConfirmView, SubscriptionView

urlpatterns = [
    path('', SubscriptionView.as_view(), name='subscription'),
    path('checkout/', CheckoutView.as_view(), name='subscription-checkout'),
    path('confirm/', ConfirmView.as_view(), name='subscription-confirm'),
    path('cancel/', CancelView.as_view(), name='subscription-cancel'),
]
