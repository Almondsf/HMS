'''Self-serve signup API, on the platform site. Anyone may call it; it is rate limited.'''

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from helpers.api import hospital_url, platform_url
from subscriptions.models import PlanPrice
from subscriptions.views import PlanPriceSerializer
from tenants.models import Hospital

from . import services


class SignupSerializer(serializers.Serializer):
    hospital_name = serializers.CharField(max_length=150)
    address = serializers.CharField(max_length=40, help_text='e.g. st-lukes, for st-lukes.<domain>')
    plan = serializers.ChoiceField(choices=Hospital.Plan.choices, default=Hospital.Plan.PRO)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    # Honeypot: hidden in the form, so only bots fill it in
    website = serializers.CharField(required=False, allow_blank=True, default='')
    accept_terms = serializers.BooleanField(help_text='The terms of service and privacy policy were accepted')

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError('Please accept the terms of service and privacy policy to continue.')
        return value

    def validate_address(self, value):
        return value.strip().lower()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)


class PublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


SENT = {'detail': 'Check your email for a link to confirm your address and create your hospital.'}


class SignupView(PublicView):
    '''Start a signup: emails a verification link. Nothing is created until it is clicked.'''

    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = 'signup'

    def post(self, request):
        data = SignupSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        details = dict(data.validated_data)
        details.pop('accept_terms')  # required to be true; the accepted versions are recorded
        if details.pop('website'):
            return Response(SENT, status=status.HTTP_201_CREATED)  # a bot: look normal, do nothing
        try:
            services.request_signup(
                **details,
                ip=request.META.get('REMOTE_ADDR'),
                verify_url=lambda token: platform_url(request, f'/signup/verify?token={token}'),
            )
        except services.EmailNotSent:
            return Response(
                {'detail': "We couldn't send the confirmation email just now. Please try again in a few minutes."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(SENT, status=status.HTTP_201_CREATED)


class AvailabilityView(PublicView):
    '''Is this hospital address free? (Addresses are public, so this reveals nothing secret.)'''

    def get(self, request):
        address = request.query_params.get('address', '').strip().lower()
        problem = services.address_problem(address)
        return Response({
            'address': address,
            'available': problem is None,
            'reason': problem or '',
            'url': hospital_url(request, address, '') if problem is None else '',
        })  # fmt: skip


class PlansView(PublicView):
    '''Prices for the signup page.'''

    def get(self, request):
        return Response({
            'trial_days': settings.SUBSCRIPTION_TRIAL_DAYS,
            'prices': PlanPriceSerializer(PlanPrice.objects.filter(is_active=True), many=True).data,
        })  # fmt: skip


class VerifyView(PublicView):
    '''The emailed link: confirms the address and starts creating the hospital.'''

    def post(self, request):
        data = TokenSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        token = data.validated_data['token']
        found = services.find(token)
        login_url = hospital_url(request, found.address, '/login') if found else ''
        signup = services.verify(token=token, login_url=login_url)
        return Response(services.describe(signup))


class StatusView(PublicView):
    '''Progress of the hospital's setup (the token stays out of URLs and logs).'''

    def post(self, request):
        data = TokenSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        signup = services.find(data.validated_data['token'])
        if signup is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(services.describe(signup))
