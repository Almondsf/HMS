from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LegalDocument


class LegalDocumentView(APIView):
    '''The current terms of service or privacy policy (public).'''

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, kind):
        if kind not in LegalDocument.Kind.values:
            raise Http404
        document = LegalDocument.current(kind)
        if document is None:
            raise Http404
        return Response({
            'kind': document.kind,
            'title': document.get_kind_display(),
            'version': document.version,
            'is_draft': document.is_draft,
            'published_at': document.published_at,
            'body': document.body,
        })  # fmt: skip
