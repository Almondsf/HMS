import re

from django.db.models import Q
from rest_framework import serializers, viewsets

from authentication.permissions import STAFF_ROLES, allow_roles
from helpers.search import search

from .models import Icd10Code


class Icd10CodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Icd10Code
        fields = ['code', 'title']


class Icd10CodeViewSet(viewsets.ReadOnlyModelViewSet):
    '''
    ICD-10 code lookup for diagnosis pick-lists: ?search=malaria, ?search=B50
    (codes match with or without the dot, e.g. b509).
    '''

    serializer_class = Icd10CodeSerializer
    permission_classes = [allow_roles(read=STAFF_ROLES)]
    filter_backends = []
    lookup_value_regex = r'[^/]+'

    def get_queryset(self):
        codes = Icd10Code.objects.filter(is_active=True)
        text = self.request.query_params.get('search', '').strip()
        if not text:
            return codes
        compact = text.replace('.', '').upper()
        by_code = codes.filter(Q(code__istartswith=text) | Q(code__regex=rf'^{_dotless(compact)}'))
        by_title = search(codes, text, ['title'])
        return (by_code | by_title).distinct()


def _dotless(compact):
    r'''Regex matching a code typed without its dot, e.g. B509 -> B50\.?9.'''
    escaped = re.escape(compact)
    return escaped[:3] + r'\.?' + escaped[3:] if len(compact) > 3 else escaped
