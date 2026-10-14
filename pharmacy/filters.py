import django_filters as filters
from django.db.models import F

from .models import DispenseTransaction, Drug


class DrugFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')
    low_stock = filters.BooleanFilter(method='filter_low_stock', help_text='true: at or below reorder level')

    class Meta:
        model = Drug
        fields = ['name']

    def filter_low_stock(self, queryset, name, value):
        low = {'quantity_in_stock__lte': F('reorder_level')}
        return queryset.filter(**low) if value else queryset.exclude(**low)


class DispenseTransactionFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name='dispensed_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='dispensed_at', lookup_expr='date__lte')

    class Meta:
        model = DispenseTransaction
        fields = ['pharmacist']
