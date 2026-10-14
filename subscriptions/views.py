import json
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.recorder import Category, record
from authentication.permissions import Role, allow_roles
from helpers.api import app_url
from tenants.models import Hospital

from . import paystack, services
from .models import Interval, PlanPrice, Subscription, SubscriptionPayment

logger = logging.getLogger('hms.subscriptions')

ADMINS_ONLY = [allow_roles(read=[Role.ADMIN], write=[Role.ADMIN])]


class PlanPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPrice
        fields = ['plan', 'interval', 'amount', 'currency']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPayment
        fields = ['reference', 'source', 'plan', 'interval', 'amount', 'currency', 'paid_at', 'period_end']


class CheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=Hospital.Plan.choices)
    interval = serializers.ChoiceField(choices=Interval.choices)


class ConfirmSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)


def _hospital():
    return Hospital.objects.get(pk=connection.tenant.pk)


def summary(hospital):
    subscription = Subscription.objects.filter(hospital=hospital).first() or services.start_trial(hospital)
    return {
        'plan': hospital.plan,
        **services.describe(subscription),
        'online_payments': bool(settings.PAYSTACK_SECRET_KEY),
    }


class SubscriptionView(APIView):
    '''The hospital's subscription: status, prices and payment history (admins).'''

    permission_classes = ADMINS_ONLY

    def get(self, request):
        hospital = _hospital()
        return Response({
            **summary(hospital),
            'prices': PlanPriceSerializer(PlanPrice.objects.filter(is_active=True), many=True).data,
            'payments': PaymentSerializer(hospital.subscription_payments.all()[:24], many=True).data,
        })  # fmt: skip


class CheckoutView(APIView):
    '''Start paying: returns a Paystack URL; the payer comes back to /subscription in the app.'''

    permission_classes = ADMINS_ONLY

    def post(self, request):
        choice = CheckoutSerializer(data=request.data)
        choice.is_valid(raise_exception=True)
        try:
            result = services.start_checkout(
                hospital=_hospital(),
                email=request.user.email,
                callback_url=app_url(request, '/subscription'),
                **choice.validated_data,
            )
        except paystack.PaystackError as exc:
            return Response({'detail': str(exc)}, status=502)
        return Response(result)


class ConfirmView(APIView):
    '''The payer is back from Paystack: verify with Paystack itself before applying anything.'''

    permission_classes = ADMINS_ONLY

    def post(self, request):
        data = ConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        hospital = _hospital()
        try:
            services.confirm_checkout(hospital=hospital, reference=data.validated_data['reference'])
        except paystack.PaystackError as exc:
            return Response({'detail': str(exc)}, status=502)
        return Response(summary(Hospital.objects.get(pk=hospital.pk)))


class CancelView(APIView):
    '''Stop auto-renewal; access continues until the paid period ends.'''

    permission_classes = ADMINS_ONLY

    def post(self, request):
        hospital = _hospital()
        try:
            services.cancel_auto_renew(hospital=hospital)
        except paystack.PaystackError as exc:
            return Response({'detail': str(exc)}, status=502)
        return Response(summary(hospital))


@csrf_exempt
@require_POST
def paystack_webhook(request):
    '''
    Paystack events (renewals, failures, cancellations). Only signed events
    are accepted. Valid events always get 200 (even when ignored) so Paystack
    stops retrying; unexpected errors return 500 so it retries later.
    '''
    if not paystack.valid_signature(request.body, request.headers.get('X-Paystack-Signature', '')):
        record('subscription.webhook_rejected', Category.SECURITY, metadata={'reason': 'bad signature'})
        return HttpResponse(status=400)
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    try:
        outcome = services.handle_webhook(event)
    except ValidationError as exc:
        outcome = f'rejected: {"; ".join(exc.messages)}'
        record(
            'subscription.webhook_rejected', Category.DOMAIN, metadata={'event': event.get('event'), 'reason': outcome}
        )
    logger.info('Paystack %s: %s', event.get('event'), outcome)
    return JsonResponse({'outcome': outcome})
