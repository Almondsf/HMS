from django.db.models import Q
from rest_framework import viewsets

from audit.mixins import AuditedReadMixin
from authentication.permissions import STAFF_ROLES, Role, allow_roles

from .models import LabTest, TestOrder, TestResult
from .serializers import LabTestSerializer, TestOrderSerializer, TestResultSerializer


def doctor_scope(user, prefix=''):
    '''Lab records a doctor may see: orders they placed or from their own visits.'''
    return Q(**{f'{prefix}ordered_by__user': user}) | Q(**{f'{prefix}consultation__visit__assigned_doctor__user': user})


class LabTestViewSet(viewsets.ModelViewSet):
    '''Test catalogue. Retire tests with is_active=false; they can't be deleted.'''

    queryset = LabTest.objects.all()
    serializer_class = LabTestSerializer
    permission_classes = [allow_roles(read=STAFF_ROLES, write=[Role.ADMIN, Role.LAB_TECHNICIAN])]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class TestOrderViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    serializer_class = TestOrderSerializer
    permission_classes = [allow_roles(read=[Role.ADMIN], write=[Role.DOCTOR, Role.LAB_TECHNICIAN])]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        orders = TestOrder.objects.select_related('patient__user', 'ordered_by__user').prefetch_related(
            'results__test', 'results__labtech__user'
        )
        user = self.request.user
        if user.user_type == Role.DOCTOR:
            return orders.filter(doctor_scope(user))
        return orders


class TestResultViewSet(AuditedReadMixin, viewsets.ModelViewSet):
    '''Results are created with their order; the lab fills them in with PATCH.'''

    serializer_class = TestResultSerializer
    permission_classes = [allow_roles(read=[Role.DOCTOR, Role.ADMIN], write=[Role.LAB_TECHNICIAN])]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        results = TestResult.objects.select_related('test', 'labtech__user', 'order').order_by(
            '-order__ordered_at', 'id'
        )
        user = self.request.user
        if user.user_type == Role.DOCTOR:
            return results.filter(doctor_scope(user, prefix='order__'))
        return results
