import django_filters as filters

from .models import Appointment


class AppointmentFilter(filters.FilterSet):
    date = filters.DateFilter(field_name='starts_at', lookup_expr='date', help_text='Day, in hospital time')
    date_from = filters.DateFilter(field_name='starts_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='starts_at', lookup_expr='date__lte')

    class Meta:
        model = Appointment
        fields = ['status', 'doctor', 'patient', 'department']
