import django_filters as filters

from .models import TestOrder, TestResult


class TestOrderFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name='ordered_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='ordered_at', lookup_expr='date__lte')

    class Meta:
        model = TestOrder
        fields = ['status', 'patient', 'consultation']


class TestResultFilter(filters.FilterSet):
    patient = filters.NumberFilter(field_name='order__patient')

    class Meta:
        model = TestResult
        fields = ['status', 'order', 'test']
