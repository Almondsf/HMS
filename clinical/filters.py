import django_filters as filters
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce

from .models import Consultation, Prescription, Visit


class VisitFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name='visit_date', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='visit_date', lookup_expr='date__lte')

    class Meta:
        model = Visit
        fields = ['status', 'patient', 'assigned_doctor']


class ConsultationFilter(filters.FilterSet):
    patient = filters.NumberFilter(field_name='visit__patient')
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Consultation
        fields = ['visit']


class PrescriptionFilter(filters.FilterSet):
    patient = filters.NumberFilter(field_name='consultation__visit__patient')
    pending = filters.BooleanFilter(method='filter_pending', help_text='true: still has units to dispense')

    class Meta:
        model = Prescription
        fields = ['consultation', 'drug']

    def filter_pending(self, queryset, name, value):
        queryset = queryset.annotate(dispensed=Coalesce(Sum('dispensed_items__quantity_dispensed'), 0))
        # No quantity given: pending until something is dispensed against it
        pending = Q(quantity__isnull=False, dispensed__lt=F('quantity')) | Q(quantity__isnull=True, dispensed=0)
        return queryset.filter(pending) if value else queryset.exclude(pending)
