'''
Platform operators choose who delivers email and SMS (platform site only):

  GET  /api/v1/platform/providers/                          what's available, configured and active
  PUT  /api/v1/platform/providers/<channel>/<provider>/      save settings  {"api_token": "...", ...}
  POST /api/v1/platform/providers/<channel>/<provider>/test/ send a test     {"to": "you@x.com"}
  PUT  /api/v1/platform/providers/<channel>/                 switch provider {"provider": "zeptomail"}
                                                             (null goes back to the server settings)
'''

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from tenants.views import IsPlatformOperator

from . import services
from .models import Channel, ProviderConfig
from .registry import PROVIDERS


def overview():
    return {
        'channels': {
            channel: dict(zip(('using', 'source'), services.status(channel), strict=True)) for channel in Channel.values
        },
        'catalog': [cls.describe() for cls in PROVIDERS.values()],
        'configs': [services.serialize(config) for config in ProviderConfig.objects.all()],
    }


class ProvidersView(APIView):
    permission_classes = [IsPlatformOperator]

    def get(self, request):
        return Response(overview())


class SwitchSerializer(serializers.Serializer):
    provider = serializers.CharField(allow_null=True)


class ChannelView(APIView):
    '''Switch the provider in use for a channel.'''

    permission_classes = [IsPlatformOperator]

    def put(self, request, channel):
        data = SwitchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.activate(channel=channel, provider=data.validated_data['provider'], by=request.user)
        return Response(overview())


class ProviderView(APIView):
    '''Save a provider's settings. Secret fields left blank keep their stored value.'''

    permission_classes = [IsPlatformOperator]

    def put(self, request, channel, provider):
        if not isinstance(request.data, dict):
            raise serializers.ValidationError('Send the settings as a JSON object.')
        config = services.save_config(channel=channel, provider=provider, values=dict(request.data), by=request.user)
        return Response(services.serialize(config))


class TestSerializer(serializers.Serializer):
    to = serializers.CharField(max_length=254, help_text='An email address or a mobile number')


class ProviderTestView(APIView):
    permission_classes = [IsPlatformOperator]

    def post(self, request, channel, provider):
        data = TestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        config = services.test_config(channel=channel, provider=provider, to=data.validated_data['to'], by=request.user)
        return Response(services.serialize(config))
