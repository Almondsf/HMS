import django_filters as filters

from .models import Invoice, Payment


class InvoiceFilter(filters.FilterSet):
    outstanding = filters.BooleanFilter(method='filter_outstanding', help_text='true: issued and not fully paid')
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Invoice
        fields = ['patient', 'visit', 'status']

    def filter_outstanding(self, queryset, name, value):
        outstanding = {'status': Invoice.Status.ISSUED}
        return queryset.filter(**outstanding) if value else queryset.exclude(**outstanding)


class PaymentFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Payment
        fields = ['invoice', 'method', 'received_by', 'voided']
