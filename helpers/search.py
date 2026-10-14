from functools import reduce
from operator import and_, or_

from django.db.models import Q


def search(queryset, text, fields):
    '''
    Every word must match at least one field (case-insensitive substring), so
    "ada obi" finds Ada Obi, and "MRN-0001 obi" narrows by both.
    '''
    words = (text or '').split()
    if not words:
        return queryset
    per_word = [reduce(or_, (Q(**{f'{field}__icontains': word}) for field in fields)) for word in words]
    return queryset.filter(reduce(and_, per_word))
